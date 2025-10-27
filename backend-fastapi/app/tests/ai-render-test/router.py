from fastapi import APIRouter, Body, HTTPException
from .parameters import PRESETS, MidiParameters, AudioRenderParameters
from .pipeline import run_midi, run_render, run_full
from .local_library import discover_samples, list_available_instruments
from .local_library import find_sample_by_id
from pathlib import Path
from .local_library import DEFAULT_LOCAL_SAMPLES_ROOT
from .inventory import build_inventory, load_inventory, INVENTORY_SCHEMA_VERSION
from .debug_store import DEBUG_STORE
from .audio_renderer import SampleMissingError
from .chat_smoke.router import router as chat_smoke_router

router = APIRouter(prefix="/ai-render-test", tags=["ai-render-test"])
SCHEMA_VERSION = "2025-10-27-1"

@router.get("/presets")
def get_presets():
    return {name: fn() for name, fn in PRESETS.items()}

@router.get("/meta")
def get_meta():
    return {
        "schema_version": SCHEMA_VERSION,
        "payload": "single-object",
        "local_samples": True,
        # Behavior: unknown instruments are auto-filtered to those available in local library
        "strict_missing_samples": False,
        "auto_filter_instruments": True,
        "endpoints": [
            "/ai-render-test/run/midi",
            "/ai-render-test/run/render",
            "/ai-render-test/run/full",
            "/ai-render-test/debug/{run_id}",
            "/ai-render-test/available-instruments",
            "/ai-render-test/samples/{instrument}",
            "/ai-render-test/chat-smoke/send",
            "/ai-render-test/chat-smoke/providers",
            "/ai-render-test/chat-smoke/models/{provider}",
            "/ai-render-test/chat-smoke/paramify",
            "/ai-render-test/chat-smoke/debug/{run_id}",
        ]
    }

@router.get("/available-instruments")
def available_instruments():
    lib = discover_samples()
    return {"available": list_available_instruments(lib), "count": len(lib)}


@router.get("/samples/{instrument}")
def list_samples_for_instrument(instrument: str, offset: int = 0, limit: int = 100):
    """List local samples for a given instrument with preview URLs.
    Only samples from that instrument bucket are returned.
    """
    lib = discover_samples()
    items = lib.get(instrument)
    if not items:
        return {"instrument": instrument, "count": 0, "items": [], "default": None}
    # slice
    start = max(0, int(offset)); end = start + max(1, min(500, int(limit)))
    out = []
    base = DEFAULT_LOCAL_SAMPLES_ROOT
    for s in items[start:end]:
        try:
            rel = Path(s.file).resolve().relative_to(base)
            url = "/api/local-samples/" + rel.as_posix()
        except Exception:
            url = None
        out.append({
            "id": s.id,
            "file": str(s.file),
            "name": s.file.name,
            "url": url,
            "subtype": getattr(s, 'subtype', None),
            "family": getattr(s, 'family', None),
            "category": getattr(s, 'category', None),
            "pitch": getattr(s, 'pitch', None),
        })
    default_item = out[0] if out else None
    return {"instrument": instrument, "count": len(items), "offset": start, "limit": limit, "items": out, "default": default_item}


DRUM_COMPONENTS = ["kick", "snare", "hihat", "clap", "808"]
# Alias/substitution map: try these candidates in order if original instrument is unavailable
ALIAS_FALLBACKS: dict[str, list[str]] = {
    # spelling/semantics
    "strings_ensemble": ["strings", "pad"],
    "string_ensemble": ["strings", "pad"],
    "stringsensemble": ["strings", "pad"],
    "orchestral_strings": ["strings", "pad"],
    "french_horn": ["lead", "misc"],
    "horn": ["lead", "misc"],
    "timpani": ["tom", "kick", "perc"],
}

def _expand_drums_if_present(midi_params: MidiParameters, available: set[str]) -> MidiParameters:
    """Allow using a virtual 'drums' instrument that expands into core drum components.
    Only components actually available are kept. If none available, 'drums' is removed.
    """
    insts = list(midi_params.instruments)
    if "drums" not in insts:
        return midi_params
    # Build expansion set intersecting available
    expanded = [d for d in DRUM_COMPONENTS if d in available]
    # Replace 'drums' with its components
    new_list: list[str] = []
    for i in insts:
        if i == "drums":
            new_list.extend(expanded)
        else:
            new_list.append(i)
    # Dedup while preserving order
    seen: set[str] = set()
    filtered: list[str] = []
    for i in new_list:
        if i not in seen:
            seen.add(i)
            filtered.append(i)
    # Rebuild params via dict to regenerate instrument_configs downstream
    payload = midi_params.to_dict()
    payload["instruments"] = filtered
    # Drop instrument_configs so pipeline recomputes aligned with instruments
    payload["instrument_configs"] = []
    return MidiParameters.from_dict(payload)

def _filter_to_available(params: MidiParameters, available: set[str]) -> MidiParameters:
    """Filter instruments in params to only those present in available set.
    Rebuild instrument_configs to align. If none remain, keep empty list.
    """
    keep = [i for i in params.instruments if i in available]
    if keep == params.instruments:
        return params
    payload = params.to_dict()
    payload["instruments"] = keep
    # Force recompute configs to match filtered set
    payload["instrument_configs"] = []
    return MidiParameters.from_dict(payload)

def _apply_alias_substitutions(params: MidiParameters, available: set[str]) -> tuple[MidiParameters, dict[str, str]]:
    """Replace unavailable instruments with best-effort fallbacks based on ALIAS_FALLBACKS.
    Returns updated params and a dict of {original: replaced} for logging/UX.
    """
    subs: dict[str, str] = {}
    out: list[str] = []
    for inst in params.instruments:
        key = str(inst).strip().lower().replace(" ", "_")
        if inst in available:
            out.append(inst)
            continue
        cands = ALIAS_FALLBACKS.get(key, [])
        chosen = None
        for c in cands:
            if c in available:
                chosen = c
                break
        if chosen is not None:
            subs[inst] = chosen
            out.append(chosen)
        else:
            out.append(inst)  # keep for later filtering
    if out == params.instruments:
        return params, subs
    payload = params.to_dict()
    payload["instruments"] = out
    payload["instrument_configs"] = []
    return MidiParameters.from_dict(payload), subs

@router.post("/run/midi")
def run_midi_endpoint(payload: dict = Body(...)):
    # Backward compatibility: allow direct MidiParameters body or wrapped under 'midi'
    midi_raw = payload if isinstance(payload, dict) and ('style' in payload or 'midi' not in payload) else (payload.get('midi') or {})
    composer_provider = payload.get('composer_provider') or None
    composer_model = payload.get('composer_model') or None
    ai_midi = payload.get('ai_midi') or None
    try:
        params = MidiParameters.from_dict(midi_raw)
    except ValueError as e:
        raise HTTPException(status_code=422, detail={"error": "validation", "message": str(e)})
    lib = discover_samples(); available = set(list_available_instruments(lib))
    # Expand virtual 'drums' then filter to only available
    params = _expand_drums_if_present(params, available)
    params, subs = _apply_alias_substitutions(params, available)
    filtered = _filter_to_available(params, available)
    if not filtered.instruments:
        raise HTTPException(status_code=422, detail={"error": "no_available_instruments", "available": sorted(available)})
    try:
        result = run_midi(filtered.to_dict(), composer_provider=composer_provider, composer_model=composer_model, ai_midi_data=ai_midi)
        if subs and isinstance(result, dict):
            # attach substitution info for UI if needed
            result.setdefault("meta", {})
            result["meta"]["instrument_substitutions"] = subs
        return result
    except SampleMissingError as e:
        raise HTTPException(status_code=422, detail={"error": "missing_samples", "message": str(e)})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": "internal", "message": str(e)})

@router.post("/run/render")
def run_render_endpoint(payload: dict = Body(...)):
    midi_raw = payload.get("midi") or {}
    audio_raw = payload.get("audio") or {}
    selected_samples = payload.get("selected_samples") or None
    try:
        midi_params = MidiParameters.from_dict(midi_raw)
        audio_params = AudioRenderParameters.from_dict(audio_raw)
    except ValueError as e:
        raise HTTPException(status_code=422, detail={"error": "validation", "message": str(e)})

    lib = discover_samples(); available = set(list_available_instruments(lib))
    midi_params = _expand_drums_if_present(midi_params, available)
    midi_params, subs = _apply_alias_substitutions(midi_params, available)
    midi_params = _filter_to_available(midi_params, available)
    if not midi_params.instruments:
        raise HTTPException(status_code=422, detail={"error": "no_available_instruments", "available": sorted(available)})

    composer_provider = payload.get('composer_provider') or None
    composer_model = payload.get('composer_model') or None
    ai_midi = payload.get('ai_midi') or None
    try:
        result = run_render(midi_params.to_dict(), audio_params.to_dict(), selected_samples=selected_samples, composer_provider=composer_provider, composer_model=composer_model, ai_midi_data=ai_midi)
        if subs and isinstance(result, dict):
            result.setdefault("meta", {})
            result["meta"]["instrument_substitutions"] = subs
        return result
    except SampleMissingError as e:
        raise HTTPException(status_code=422, detail={"error": "missing_samples", "message": str(e)})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": "internal", "message": str(e)})

@router.post("/run/full")
def run_full_endpoint(payload: dict = Body(...)):
    midi_raw = payload.get("midi") or {}
    audio_raw = payload.get("audio") or {}
    selected_samples = payload.get("selected_samples") or None
    try:
        midi_params = MidiParameters.from_dict(midi_raw)
        audio_params = AudioRenderParameters.from_dict(audio_raw)
    except ValueError as e:
        raise HTTPException(status_code=422, detail={"error": "validation", "message": str(e)})

    lib = discover_samples(); available = set(list_available_instruments(lib))
    midi_params = _expand_drums_if_present(midi_params, available)
    midi_params, subs = _apply_alias_substitutions(midi_params, available)
    midi_params = _filter_to_available(midi_params, available)
    if not midi_params.instruments:
        raise HTTPException(status_code=422, detail={"error": "no_available_instruments", "available": sorted(available)})

    composer_provider = payload.get('composer_provider') or None
    composer_model = payload.get('composer_model') or None
    try:
        result = run_full(midi_params.to_dict(), audio_params.to_dict(), selected_samples=selected_samples, composer_provider=composer_provider, composer_model=composer_model)
        if subs and isinstance(result, dict):
            result.setdefault("meta", {})
            result["meta"]["instrument_substitutions"] = subs
        return result
    except SampleMissingError as e:
        raise HTTPException(status_code=422, detail={"error": "missing_samples", "message": str(e)})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": "internal", "message": str(e)})

@router.get("/debug/{run_id}")
def get_debug(run_id: str):
    data = DEBUG_STORE.get(run_id)
    return data or {"error": "not_found"}

@router.post("/inventory/rebuild")
def rebuild_inventory(mode: str | None = None):
    deep = (mode == "deep")
    inv = build_inventory(deep=deep)
    return {"rebuilt": True, "deep": deep, "schema_version": inv.get("schema_version"), "instrument_count": inv.get("instrument_count"), "total_files": inv.get("total_files")}

@router.get("/inventory")
def get_inventory():
    inv = load_inventory()
    if inv is None:
        inv = build_inventory()
    return {"schema_version": inv.get("schema_version"), **inv}

# Mount nested chat smoke endpoints
router.include_router(chat_smoke_router)
