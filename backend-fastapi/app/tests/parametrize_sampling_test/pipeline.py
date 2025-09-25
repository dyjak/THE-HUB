from __future__ import annotations
from .debug_store import DEBUG_STORE
from .parameters import MidiParameters, AudioRenderParameters
from .midi_engine import generate_midi
from .local_library import discover_samples, select_local_sample, list_available_instruments
from .audio_renderer import render_audio, SampleMissingError
from pathlib import Path
import json, time


def _collect_instruments(midi_params: dict) -> list[str]:
    return midi_params.get("instruments") or []


def run_midi(midi_params: dict):
    run = DEBUG_STORE.start()
    run.log("meta", "module_version", {"module": "parametrize_sampling_test", "version": "0.1.0"})
    run.log("run", "midi_phase")
    run.log("call", "generate_midi", {})
    midi_data = generate_midi(midi_params, run.log)
    run.log("run", "midi_generated", {"bars": len(midi_data.get('pattern', []))})
    # Persist a simple JSON representation (placeholder for real .mid export)
    out_dir = Path(__file__).parent / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    midi_filename = f"midi_{int(time.time())}_{run.run_id}.json"
    midi_path = out_dir / midi_filename
    try:
        with midi_path.open('w', encoding='utf-8') as f:
            json.dump(midi_data, f)
        run.log("midi", "saved", {"file": str(midi_path)})
    except Exception as e:
        run.log("midi", "save_failed", {"error": str(e)})
    run.log("run", "completed")
    return {"run_id": run.run_id, "midi": midi_data, "midi_file": str(midi_path), "debug": DEBUG_STORE.get(run.run_id)}


def _prepare_local_samples(instruments: list[str], run_log):
    library = discover_samples()
    run_log("samples", "library_indexed", {"instruments_indexed": len(library), "available": list_available_instruments(library)})
    selected = []
    for idx, inst in enumerate(instruments):
        s = select_local_sample(inst, idx, library)
        if s:
            selected.append({
                "instrument": inst,
                "id": s.id,
                "file": str(s.file),
                "source": s.source,
            })
            run_log("samples", "instrument_sample_selected", {"instrument": inst, "file": str(s.file)})
        else:
            run_log("samples", "instrument_sample_missing", {"instrument": inst})
    return {"samples": selected}


def run_render(midi_params: dict, audio_params: dict):
    run = DEBUG_STORE.start()
    run.log("meta", "module_version", {"module": "parametrize_sampling_test", "version": "0.1.0"})
    run.log("run", "render_phase")
    run.log("call", "generate_midi", {})
    midi_data = generate_midi(midi_params, run.log)
    instruments = midi_data.get("meta", {}).get("instruments", [])
    run.log("call", "prepare_local_samples", {"count": len(instruments)})
    samples = _prepare_local_samples(instruments, run.log)
    if len(samples.get("samples", [])) != len(instruments):
        have = [s['instrument'] for s in samples['samples']]
        missing = [i for i in instruments if i not in have]
        run.log("samples", "missing_required", {"expected": instruments, "have": have, "missing": missing})
        run.log("run", "failed", {"reason": "missing_samples", "missing": missing})
        raise SampleMissingError(f"Missing required samples for: {', '.join(missing)}")
    run.log("call", "render_audio", {})
    try:
        audio = render_audio(audio_params, midi_data, samples, run.log)
    except SampleMissingError as e:
        run.log("audio", "render_failed", {"error": str(e)})
        run.log("run", "failed", {"reason": "audio", "error": str(e)})
        raise
    run.log("run", "audio_rendered", {"file": audio.get('audio_file')})
    run.log("run", "completed")
    return {"run_id": run.run_id, "midi": midi_data, "samples": samples, "audio": audio, "debug": DEBUG_STORE.get(run.run_id)}


def run_full(midi_params: dict, audio_params: dict):
    # For this simplified module, run_full == run_render
    return run_render(midi_params, audio_params)
