from fastapi import APIRouter
from pathlib import Path
from .parameters import PRESETS, MidiParameters, SampleSelectionParameters, AudioRenderParameters
from .pipeline import run_midi, run_render, run_full
from .debug_store import DEBUG_STORE

router = APIRouter(prefix="/param-adv", tags=["param-adv"])


@router.get("/presets")
def get_presets():
    return {name: fn() for name, fn in PRESETS.items()}


@router.post("/run/midi")
def run_midi_endpoint(params: MidiParameters):
    return run_midi(params.to_dict())


@router.post("/run/render")
def run_render_endpoint(midi: MidiParameters, samples: SampleSelectionParameters, audio: AudioRenderParameters):
    return run_render(midi.to_dict(), samples.to_dict(), audio.to_dict())


@router.post("/run/full")
def run_full_endpoint(midi: MidiParameters, samples: SampleSelectionParameters, audio: AudioRenderParameters):
    return run_full(midi.to_dict(), samples.to_dict(), audio.to_dict())


@router.get("/debug/{run_id}")
def get_debug(run_id: str):
    data = DEBUG_STORE.get(run_id)
    return data or {"error": "not_found"}


@router.get("/docs")
def get_docs():
    readme_path = Path(__file__).parent / "README.md"
    if not readme_path.exists():
        return {"error": "readme_missing"}
    content = readme_path.read_text(encoding="utf-8")
    return {"readme": content}
