from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from pathlib import Path
import json
import os

from .schemas import MidiPlanIn, MidiPlanResult
from urllib.parse import quote
try:
    from app.air.inventory.access import get_inventory_cached as _inv_get_cached
    from app.air.inventory.access import list_instruments as _inv_list
except Exception:  # pragma: no cover
    _inv_get_cached = None  # type: ignore
    _inv_list = None  # type: ignore
try:  # optional inventory usage for hints
    from app.air.inventory.access import list_instruments as _inventory_instruments
except Exception:
    _inventory_instruments = None  # type: ignore
from .debug_store import DEBUG_STORE

# Lazy import helpers to avoid hard dependency at import-time (main may synthesize packages)
def _get_clients():
    """Late import of provider client helpers.

    We look for the ai-render-test module first (newer), then ai-param-test as fallback.
    This avoids hard import errors if one variant isn't present.
    """
    errors = []
    for pkg in ("ai_render_test", "ai_param_test"):
        try:
            base = f"app.tests.{pkg}.chat_smoke.client"
            mod = __import__(base, fromlist=["get_openai_client"])
            get_openai_client = getattr(mod, "get_openai_client")
            get_anthropic_client = getattr(mod, "get_anthropic_client")
            get_gemini_client = getattr(mod, "get_gemini_client")
            _list_providers = getattr(mod, "list_providers")
            _list_models = getattr(mod, "list_models")
            return get_openai_client, get_anthropic_client, get_gemini_client, _list_providers, _list_models
        except Exception as e:  # pragma: no cover
            errors.append(f"{pkg}: {e}")
            continue
    raise RuntimeError("param-generation: provider clients unavailable; attempted: " + "; ".join(errors))


router = APIRouter(prefix="/air/param-generation", tags=["air:param-generation"])

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class ProvidersOut(BaseModel):
    providers: list[dict]


@router.get("/providers", response_model=ProvidersOut)
def providers() -> ProvidersOut:
    _get_openai, _get_anthropic, _get_gemini, _list_providers, _list_models = _get_clients()
    items = _list_providers()
    return ProvidersOut(providers=items)


@router.get("/models/{provider}")
def models(provider: str):
    _get_openai, _get_anthropic, _get_gemini, _list_providers, _list_models = _get_clients()
    return {"provider": provider, "models": _list_models(provider)}


def _allowed_instruments_hint() -> str:
    # Prefer inventory (canonical list, may include future instruments)
    try:
        if callable(_inventory_instruments):  # type: ignore
            inv_list = _inventory_instruments() or []
            if inv_list:
                return ", ".join(inv_list)
    except Exception:
        pass
    # Final static fallback (no ai-render-test dependency)
    return "piano, pad, strings, lead, bass, drumkit, kick, snare, hihat, fx"


def _midi_plan_system(midi: MidiPlanIn) -> tuple[str, str]:
    allowed = _allowed_instruments_hint()
    system = (
        "You are a precise MIDI planner. Respond ONLY with valid minified JSON in the exact schema:"
        " {\"pattern\":[{\"bar\":number,\"events\":[{\"step\":number,\"note\":number,\"vel\":number,\"len\":number}]}],"
        " \"layers\":{\"<instrument>\":[{\"bar\":number,\"events\":[{\"step\":number,\"note\":number,\"vel\":number,\"len\":number}]}]},"
        " \"meta\":{\"tempo\":number,\"instruments\":[string],\"seed\":number|null}}."
        f" Use exactly {midi.bars} bars; each bar index starts at 0; steps are integers in [0..7]; len >= 1; vel in [1..127]."
        f" Instruments must be exactly these (order preserved): {midi.instruments}. Do not invent others."
        f" meta.tempo must be {midi.tempo}. meta.seed may be null or a number."
        " The combined pattern must reflect the union of all layers (merge per-bar events)."
        " Musicality: respect style/mood; bass lower register; lead higher; pads sustained (len 2-4)."
        " IMPORTANT: Allowed instrument names are strictly: [" + allowed + "]."
        " No markdown, no comments."
    )
    user = json.dumps({
        "task": "compose_midi_layers",
        "context": {
            "style": midi.style,
            "mood": midi.mood,
            "key": midi.key,
            "scale": midi.scale,
            "meter": midi.meter,
            "dynamic_profile": midi.dynamic_profile,
            "arrangement_density": midi.arrangement_density,
            "harmonic_color": midi.harmonic_color,
        },
        "tempo": midi.tempo,
        "bars": midi.bars,
        "instruments": midi.instruments,
        "seed": midi.seed,
    }, separators=(",", ":"))
    return system, user


def _call_model(provider: str, model: Optional[str], system: str, user: str) -> str:
    provider = (provider or "gemini").lower()
    _get_openai, _get_anthropic, _get_gemini, _list_providers, _list_models = _get_clients()
    if provider == "openai":
        client = _get_openai()
        use_model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        resp = client.chat.completions.create(
            model=use_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.0,
        )
        return (resp.choices[0].message.content or "").strip()
    if provider == "anthropic":
        client = _get_anthropic()
        use_model = model or os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-latest")
        resp = client.messages.create(
            model=use_model,
            system=system,
            messages=[{"role": "user", "content": user}],
            max_tokens=2048,
            temperature=0.0,
        )
        blocks = getattr(resp, "content", []) or []
        out = []
        for b in blocks:
            t = getattr(b, "text", None)
            if t:
                out.append(t)
        return "\n".join(out).strip()
    if provider == "gemini":
        g = _get_gemini()
        use_model = model or os.getenv("GOOGLE_MODEL", "gemini-2.5-flash")
        m = g.GenerativeModel(use_model, system_instruction=system)
        r = m.generate_content(user)
        return (getattr(r, "text", None) or str(r) or "").strip()
    raise HTTPException(status_code=400, detail={"error": "unknown_provider", "message": f"Unknown provider: {provider}"})


# Inventory proxy endpoints (keep param-generation self-contained for UI)
@router.get("/available-instruments")
def available_instruments_proxy():
    try:
        if callable(_inv_list):  # type: ignore
            lst = _inv_list() or []
            return {"available": lst, "count": len(lst)}
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": "inventory_unavailable", "message": str(e)})
    return {"available": [], "count": 0}


def _resolve_target_instruments(inv: dict, name: str) -> list[str]:
    names = list((inv.get("instruments") or {}).keys()) if isinstance(inv.get("instruments"), dict) else []
    if not names:
        return []
    lower_map = {n.lower(): n for n in names}
    q = (name or "").strip()
    ql = q.lower()

    # Helpers to aggregate groups from available names
    def _present(opts: list[str]) -> list[str]:
        return [x for x in opts if x in names]

    # synonyms / normalization -> singular instrument naming
    syn = {
        "pad": "Pad", "pads": "Pad",
        "bell": "Bell", "bells": "Bell",
        "pluck": "Pluck", "plucks": "Pluck",
        "lead": "Lead", "leads": "Lead",
        "synth": "Synth", "reese": "Reese",
        "bass": "Bass", "bass guitar": "Bass Guitar", "bass synth": "Bass Synth",
        "flute": "Flute", "guitar": "Guitar", "sax": "Sax",
        "piano": "Piano", "violin": "Violin", "brass": "Brass",
        "808": "808",
        # drum parts
        "kick": "Kick", "snare": "Snare", "clap": "Clap",
        "hihat": "Hat", "hi-hat": "Hat", "hats": "Hat", "hat": "Hat", "hh": "Hat",
    }

    # Exact
    if q in names:
        return [q]
    # Case-insensitive exact
    if ql in lower_map:
        return [lower_map[ql]]

    # Group aggregators
    if ql in ("drums", "drumkit"):
        agg = _present(["Kick", "Snare", "Hat", "Clap"]) or _present(["Kick", "Snare", "Hats", "Claps"])  # tolerate legacy plural
        return agg
    if ql == "fx":
        fx_opts = ["Texture", "Downfilter", "Impact", "Swell", "Riser", "Subdrop", "Upfilter"]
        return _present(fx_opts)

    # Synonym resolution to a single instrument
    if ql in syn:
        tgt = syn[ql]
        if tgt in names:
            return [tgt]
        if tgt.lower() in lower_map:
            return [lower_map[tgt.lower()]]

    # Pluralization tweaks
    if ql.endswith("s") and ql[:-1] in lower_map:
        return [lower_map[ql[:-1]]]
    if (ql + "s") in lower_map:
        return [lower_map[ql + "s"]]

    # Prefix/contains fuzzy (last resort)
    for n in names:
        if ql and (n.lower().startswith(ql) or ql in n.lower()):
            return [n]
    return []


@router.get("/samples/{instrument}")
def list_samples_proxy(instrument: str, offset: int = 0, limit: int = 100):
    if not callable(_inv_get_cached):
        raise HTTPException(status_code=500, detail={"error": "inventory_unavailable"})
    try:
        inv = _inv_get_cached()
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": "inventory_error", "message": str(e)})
    ql = (instrument or "").strip().lower()
    # Category aggregators based on sample rows for robustness
    targets: list[str] = []
    if ql in ("drums", "drumkit"):
        try:
            cat_rows = [r for r in (inv.get("samples") or []) if (r.get("category") == "Drums")]
            parts = sorted({r.get("instrument") for r in cat_rows if r.get("instrument")})
            targets = [t for t in parts if isinstance(t, str)]
        except Exception:
            targets = []
    elif ql == "fx":
        try:
            fx_rows = [r for r in (inv.get("samples") or []) if (r.get("category") == "FX")]
            parts = sorted({r.get("instrument") for r in fx_rows if r.get("instrument")})
            targets = [t for t in parts if isinstance(t, str)]
        except Exception:
            targets = []
    else:
        targets = _resolve_target_instruments(inv, instrument)
    if not targets:
        # Include resolved targets info for easier debugging/UX on the client
        return {"instrument": instrument, "resolved": [], "count": 0, "items": [], "default": None}
    tset = set(targets)
    rows = [r for r in (inv.get("samples") or []) if r.get("instrument") in tset]
    if not rows:
        return {"instrument": instrument, "resolved": targets, "count": 0, "items": [], "default": None}
    start = max(0, int(offset)); end = start + max(1, min(500, int(limit)))
    base = Path(inv.get("root") or ".").resolve()
    items: list[dict[str, Any]] = []
    for r in rows[start:end]:
        url = None
        try:
            rel = r.get("file_rel")
            if rel:
                rel_posix = Path(rel).as_posix()
                url = "/api/local-samples/" + quote(rel_posix, safe="/")
            elif r.get("file_abs"):
                rel2 = Path(r.get("file_abs")).resolve().relative_to(base).as_posix()
                url = "/api/local-samples/" + quote(rel2, safe="/")
        except Exception:
            url = None
        name = None
        try:
            if r.get("file_abs"):
                name = Path(r.get("file_abs")).name
            elif r.get("file_rel"):
                name = Path(r.get("file_rel")).name
        except Exception:
            name = r.get("id")
        items.append({
            "id": r.get("id"),
            "file": r.get("file_abs") or str((base / (r.get("file_rel") or "")).resolve()),
            "name": name,
            "url": url,
            "subtype": r.get('subtype'),
            "family": r.get('family'),
            "category": r.get('category'),
            "pitch": r.get('pitch'),
        })
    default_item = items[0] if items else None
    return {"instrument": instrument, "resolved": targets, "count": len(rows), "offset": start, "limit": limit, "items": items, "default": default_item}


class MidiPlanRequest(BaseModel):
    midi: Dict[str, Any]
    provider: Optional[str] = None
    model: Optional[str] = None


@router.post("/midi-plan")
def midi_plan(body: MidiPlanRequest):
    run = DEBUG_STORE.start()
    run.log("plan", "start", {"provider": body.provider or "gemini", "model": body.model or None})
    try:
        midi = MidiPlanIn(**(body.midi or {}))
    except Exception as e:
        raise HTTPException(status_code=422, detail={"error": "validation", "message": str(e)})

    system, user = _midi_plan_system(midi)
    try:
        run.log("provider_call", "request", {"provider": (body.provider or "gemini"), "model": (body.model or None)})
        raw = _call_model(body.provider or "gemini", body.model, system, user)
        run.log("provider_call", "raw_received", {"chars": len(raw)})
    except Exception as e:
        run.log("provider_call", "failed", {"error": str(e)})
        raise HTTPException(status_code=400, detail={"error": "provider_error", "message": str(e)})

    parsed = None
    errors: list[str] = []
    try:
        candidate = json.loads(raw)
        if isinstance(candidate, dict):
            parsed = candidate
        else:
            errors.append("parse: top-level JSON must be an object")
            run.log("parse", "json_error", {"error": "top_level_not_object"})
    except Exception as e:
        errors.append(f"parse: {e}")
        run.log("parse", "json_error", {"error": str(e)})

    # Persist outputs
    run_dir = OUTPUT_DIR / f"{json.dumps(None) or ''}"
    # fix: use run_id in directory name with timestamp
    from datetime import datetime
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    run_dir = OUTPUT_DIR / f"{ts}_{run.run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)
    raw_path = run_dir / "midi_plan_raw.txt"
    json_path = run_dir / "midi_plan.json"
    try:
        with raw_path.open("w", encoding="utf-8") as f:
            f.write(raw)
        run.log("persist", "raw_saved", {"file": str(raw_path)})
    except Exception as e:
        run.log("persist", "raw_failed", {"error": str(e)})
    if isinstance(parsed, dict):
        try:
            with json_path.open("w", encoding="utf-8") as f:
                json.dump(parsed, f)
            run.log("persist", "json_saved", {"file": str(json_path)})
        except Exception as e:
            run.log("persist", "json_failed", {"error": str(e)})

    # Build relative helpers
    def _rel(p: Path | None) -> str | None:
        if p is None:
            return None
        try:
            return str(p.relative_to(OUTPUT_DIR))
        except Exception:
            return p.name

    result: Dict[str, Any] = {
        "run_id": run.run_id,
        "raw": raw,
        "parsed": parsed,
        "errors": errors or None,
        "saved_raw_rel": _rel(raw_path),
        "saved_json_rel": _rel(json_path) if isinstance(parsed, dict) else None,
    }
    run.log("plan", "completed", {"ok": parsed is not None, "errors": (errors[:1] if errors else None)})
    return result


@router.get("/debug/{run_id}")
def get_debug(run_id: str):
    data = DEBUG_STORE.get(run_id)
    if not data:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "run not found"})
    return data
