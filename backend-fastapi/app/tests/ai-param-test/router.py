from fastapi import APIRouter, Body, HTTPException
from .parameters import PRESETS, MidiParameters, AudioRenderParameters
from .pipeline import run_midi, run_render, run_full
from .local_library import discover_samples, list_available_instruments
from .inventory import build_inventory, load_inventory, INVENTORY_SCHEMA_VERSION
from .debug_store import DEBUG_STORE
from .audio_renderer import SampleMissingError

router = APIRouter(prefix="/ai-param-test", tags=["ai-param-test"])
SCHEMA_VERSION = "2025-10-05-1"

@router.get("/presets")
def get_presets():
    return {name: fn() for name, fn in PRESETS.items()}

@router.get("/meta")
def get_meta():
    return {
        "schema_version": SCHEMA_VERSION,
        "payload": "single-object",
        "local_samples": True,
        "strict_missing_samples": True,
        "endpoints": [
            "/ai-param-test/run/midi",
            "/ai-param-test/run/render",
            "/ai-param-test/run/full",
            "/ai-param-test/debug/{run_id}",
            "/ai-param-test/available-instruments",
        ]
    }

@router.get("/available-instruments")
def available_instruments():
    lib = discover_samples()
    return {"available": list_available_instruments(lib), "count": len(lib)}

@router.post("/run/midi")
def run_midi_endpoint(params: MidiParameters):
    lib = discover_samples(); available = set(list_available_instruments(lib))
    bad = [i for i in params.instruments if i not in available]
    if bad:
        raise HTTPException(status_code=422, detail={"error": "unknown_instruments", "unknown": bad, "available": sorted(available)})
    try:
        return run_midi(params.to_dict())
    except SampleMissingError as e:
        raise HTTPException(status_code=422, detail={"error": "missing_samples", "message": str(e)})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": "internal", "message": str(e)})

@router.post("/run/render")
def run_render_endpoint(payload: dict = Body(...)):
    midi_raw = payload.get("midi") or {}
    audio_raw = payload.get("audio") or {}
    try:
        midi_params = MidiParameters.from_dict(midi_raw)
        audio_params = AudioRenderParameters.from_dict(audio_raw)
    except ValueError as e:
        raise HTTPException(status_code=422, detail={"error": "validation", "message": str(e)})

    lib = discover_samples(); available = set(list_available_instruments(lib))
    req = midi_params.instruments
    bad = [i for i in req if i not in available]
    if bad:
        raise HTTPException(status_code=422, detail={"error": "unknown_instruments", "unknown": bad, "available": sorted(available)})

    try:
        return run_render(midi_params.to_dict(), audio_params.to_dict())
    except SampleMissingError as e:
        raise HTTPException(status_code=422, detail={"error": "missing_samples", "message": str(e)})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": "internal", "message": str(e)})

@router.post("/run/full")
def run_full_endpoint(payload: dict = Body(...)):
    midi_raw = payload.get("midi") or {}
    audio_raw = payload.get("audio") or {}
    try:
        midi_params = MidiParameters.from_dict(midi_raw)
        audio_params = AudioRenderParameters.from_dict(audio_raw)
    except ValueError as e:
        raise HTTPException(status_code=422, detail={"error": "validation", "message": str(e)})

    lib = discover_samples(); available = set(list_available_instruments(lib))
    req = midi_params.instruments
    bad = [i for i in req if i not in available]
    if bad:
        raise HTTPException(status_code=422, detail={"error": "unknown_instruments", "unknown": bad, "available": sorted(available)})

    try:
        return run_full(midi_params.to_dict(), audio_params.to_dict())
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
