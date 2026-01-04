from fastapi import APIRouter, Body, Query
from pathlib import Path
from .parameters import PRESETS, MidiParameters, SampleSelectionParameters, AudioRenderParameters
from .pipeline import run_midi, run_render, run_full
from .debug_store import DEBUG_STORE
try:
    from ..sample_fetcher import SampleFetcher  # type: ignore
except Exception:
    SampleFetcher = None  # type: ignore

router = APIRouter(prefix="/param-adv", tags=["param-adv"])

# Runtime banner for quick verification in server console
SCHEMA_VERSION = "2025-09-23-1"
try:
    import os
    freesound = bool(os.environ.get("FREESOUND_API_KEY"))
    print(f"[param-adv] router loaded | schema={SCHEMA_VERSION} | payload=single-object | samples_optional=True | freesound={freesound} | file={__file__}")
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
    import os
    return {
        "schema_version": SCHEMA_VERSION,
        "payload": "single-object",
        "samples_optional": True,
        "freesound": bool(os.environ.get("FREESOUND_API_KEY")),
        "endpoints": [
            "/param-adv/run/midi",
            "/param-adv/run/render",
            "/param-adv/run/full",
            "/param-adv/debug/{run_id}",
            "/param-adv/_sample-providers",
            "/param-adv/_probe-samples",
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


@router.get("/_sample-providers")
def get_sample_providers():
    import os
    freesound_flag = bool(os.environ.get("FREESOUND_API_KEY"))
    basics_instruments = []
    provider_status = {"basic": True, "commons": True, "freesound": freesound_flag}
    try:
        if SampleFetcher is not None:
            f = SampleFetcher()
            basics = f.get_basic_samples()
            basics_instruments = sorted({s.instrument for s in basics.values()})
    except Exception as e:
        provider_status["error"] = str(e)
    return {
        "freesound": freesound_flag,
        "providers": provider_status,
        "basic_instruments": basics_instruments,
    }


@router.get("/_probe-samples")
def probe_samples(inst: str = Query(..., description="Instrument name to probe"),
                  genre: str = Query("ambient"),
                  mood: str | None = Query(None)):
    if SampleFetcher is None:
        return {"ok": False, "error": "SampleFetcher unavailable"}
    try:
        f = SampleFetcher()
        mapping = f.get_samples_for_genre(genre, mood=mood)
        candidates = mapping.get(inst) or []
        out = [
            {
                "id": c.id,
                "name": c.name,
                "instrument": c.instrument,
                "source": getattr(c, "source", None),
                "url": c.url,
                "duration": c.duration,
            }
            for c in candidates
        ]
        return {"ok": True, "count": len(out), "instrument": inst, "genre": genre, "mood": mood, "candidates": out}
    except Exception as e:
        return {"ok": False, "error": str(e)}
