from fastapi import APIRouter, Body
from .parameters import PRESETS, MidiParameters, AudioRenderParameters
from .pipeline import run_midi, run_render, run_full
from .local_library import discover_samples, list_available_instruments
from .debug_store import DEBUG_STORE

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
    return run_midi(params.to_dict())

@router.post("/run/render")
def run_render_endpoint(payload: dict = Body(...)):
    midi = payload.get("midi", {})
    audio = payload.get("audio", {})
    return run_render(midi, audio)

@router.post("/run/full")
def run_full_endpoint(payload: dict = Body(...)):
    midi = payload.get("midi", {})
    audio = payload.get("audio", {})
    return run_full(midi, audio)

@router.get("/debug/{run_id}")
def get_debug(run_id: str):
    data = DEBUG_STORE.get(run_id)
    return data or {"error": "not_found"}
