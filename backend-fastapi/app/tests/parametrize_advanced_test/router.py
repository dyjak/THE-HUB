from fastapi import APIRouter, Body
from pathlib import Path
from .parameters import PRESETS, MidiParameters, SampleSelectionParameters, AudioRenderParameters
from .pipeline import run_midi, run_render, run_full
from .debug_store import DEBUG_STORE

router = APIRouter(prefix="/param-adv", tags=["param-adv"])

# Runtime banner for quick verification in server console
SCHEMA_VERSION = "2025-09-22-1"
try:
    import os
    print(f"[param-adv] router loaded | schema={SCHEMA_VERSION} | payload=single-object | samples_optional=True | file={__file__}")
except Exception:
    # In case stdout is redirected or unavailable
    pass


@router.get("/presets")
def get_presets():
    return {name: fn() for name, fn in PRESETS.items()}


@router.get("/meta")
def get_meta():
    """Lightweight runtime hint about the expected request schema.

    Useful to verify the server picked up the latest router (single-payload endpoints).
    """
    return {
        "schema_version": "2025-09-22-1",
        "payload": "single-object",
        "samples_optional": True,
        "endpoints": [
            "/param-adv/run/midi",
            "/param-adv/run/render",
            "/param-adv/run/full",
            "/param-adv/debug/{run_id}",
        ],
    }


@router.get("/probe")
def probe():
    return {
        "ok": True,
        "schema_version": SCHEMA_VERSION,
        "file": __file__,
    }


@router.post("/run/midi")
def run_midi_endpoint(params: MidiParameters):
    return run_midi(params.to_dict())


@router.post("/run/render")
def run_render_endpoint(payload: dict = Body(...)):
    midi = payload.get("midi", {})
    audio = payload.get("audio", {})
    samples = payload.get("samples", {}) or {}
    return run_render(midi, samples, audio)


@router.post("/run/full")
def run_full_endpoint(payload: dict = Body(...)):
    midi = payload.get("midi", {})
    audio = payload.get("audio", {})
    samples = payload.get("samples", {}) or {}
    return run_full(midi, samples, audio)


@router.get("/debug/{run_id}")
def get_debug(run_id: str):
    data = DEBUG_STORE.get(run_id)
    return data or {"error": "not_found"}


@router.post("/echo")
def echo_payload(payload: dict = Body(...)):
    """Debug endpoint: returns the received JSON payload unchanged."""
    return {"received": payload}


@router.get("/docs")
def get_docs():
    readme_path = Path(__file__).parent / "README.md"
    if not readme_path.exists():
        return {"error": "readme_missing"}
    content = readme_path.read_text(encoding="utf-8")
    return {"readme": content}
