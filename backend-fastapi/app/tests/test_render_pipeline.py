from __future__ import annotations
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_render_pipeline_smoke() -> None:
    """Smoke test: param -> midi -> render pipeline produces audio files.

    This assumes inventory.json is present and at least one instrument has
    a valid sample. The goal is to catch regressions in the end-to-end
    flow rather than validate audio quality.
    """

    # 1) Call a simple MIDI generation test endpoint if available,
    #    else fall back to a minimal handcrafted midi structure.
    midi_payload = {
        "run_id": "test-run-e2e",
        "midi": {
            "meta": {"bars": 2, "instruments": ["pad"], "length_seconds": 4.0},
            "layers": {
                "pad": [
                    {"bar": 0, "events": [{"step": 0, "note": 60, "vel": 100}]},
                    {"bar": 1, "events": [{"step": 4, "note": 64, "vel": 110}]},
                ]
            },
        },
    }

    # 2) Call render endpoint directly (bypassing LLM steps for a quick test)
    render_payload = {
        "project_name": "test_project_render",
        "run_id": midi_payload["run_id"],
        "midi": midi_payload["midi"],
        "tracks": [
            {
                "instrument": "pad",
                "enabled": True,
                "volume_db": -6.0,
                "pan": 0.0,
                "eq": None,
                "compressor": None,
                "reverb": {"enabled": False, "mix": 0.0},
                "delay": {"enabled": False, "mix": 0.0},
            }
        ],
        "selected_samples": {},  # let render engine pick first available one
    }

    resp = client.post("/api/air/render/render-audio", json=render_payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert "mix_wav_rel" in data and data["mix_wav_rel"]
    assert isinstance(data["stems"], list)
    assert data["sample_rate"] > 0
    assert data["duration_seconds"] > 0

    # verify mix file exists on disk
    root = Path(__file__).resolve().parents[1] / "air" / "render" / "output"
    mix_rel = data["mix_wav_rel"]
    mix_path = root.parent / mix_rel  # mix_wav_rel is relative to OUTPUT_ROOT.parent
    assert mix_path.exists(), f"Expected mix file at {mix_path}"
