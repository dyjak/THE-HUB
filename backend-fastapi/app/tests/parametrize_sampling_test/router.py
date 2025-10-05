from fastapi import APIRouter, Body, HTTPException
from .parameters import PRESETS, MidiParameters, AudioRenderParameters
from .pipeline import run_midi, run_render, run_full
from .local_library import discover_samples, list_available_instruments
from .inventory import build_inventory, load_inventory, INVENTORY_SCHEMA_VERSION
from .debug_store import DEBUG_STORE
from .audio_renderer import SampleMissingError

router = APIRouter(prefix="/param-sampling", tags=["param-sampling"])
SCHEMA_VERSION = "2025-09-25-1"

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
            "/param-sampling/run/midi",
            "/param-sampling/run/render",
            "/param-sampling/run/full",
            "/param-sampling/debug/{run_id}",
            "/param-sampling/available-instruments",
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
    midi = payload.get("midi", {})
    audio = payload.get("audio", {})
    lib = discover_samples(); available = set(list_available_instruments(lib))
    req = midi.get("instruments") or []
    bad = [i for i in req if i not in available]
    if bad:
        raise HTTPException(status_code=422, detail={"error": "unknown_instruments", "unknown": bad, "available": sorted(available)})
    try:
        return run_render(midi, audio)
    except SampleMissingError as e:
        raise HTTPException(status_code=422, detail={"error": "missing_samples", "message": str(e)})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": "internal", "message": str(e)})

@router.post("/run/full")
def run_full_endpoint(payload: dict = Body(...)):
    midi = payload.get("midi", {})
    audio = payload.get("audio", {})
    lib = discover_samples(); available = set(list_available_instruments(lib))
    req = midi.get("instruments") or []
    bad = [i for i in req if i not in available]
    if bad:
        raise HTTPException(status_code=422, detail={"error": "unknown_instruments", "unknown": bad, "available": sorted(available)})
    try:
        return run_full(midi, audio)
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
