from __future__ import annotations
from .debug_store import DEBUG_STORE
from .parameters import MidiParameters, SampleSelectionParameters, AudioRenderParameters
from .midi_engine import generate_midi, save_midi
from .midi_visualizer import generate_pianoroll
from .sample_library import select_samples
from .audio_renderer import render_audio


def run_midi(midi_params: dict):
    run = DEBUG_STORE.start()
    run.log("meta", "module_version", {"module": "parametrize_advanced_test", "version": "0.1.0"})
    run.log("run", "midi_phase")
    run.log("run", "params_received", {"midi_keys": list(midi_params.keys())})
    run.log("func", "enter", {"module": "pipeline.py", "function": "run_midi"})
    run.log("call", "generate_midi", {"module": "midi_engine.py"})
    midi_data = generate_midi(midi_params, run.log)
    pianoroll = generate_pianoroll(midi_data, run.log)
    run.log("call", "save_midi", {"module": "midi_engine.py"})
    midi_file = save_midi(midi_data, run.log)
    run.log("run", "midi_generated", {"has_file": bool(midi_file)})
    run.log("run", "completed")
    run.log("func", "exit", {"module": "pipeline.py", "function": "run_midi"})
    return {"run_id": run.run_id, "midi": midi_data, "midi_file": midi_file, "midi_image": pianoroll, "debug": DEBUG_STORE.get(run.run_id)}


def run_render(midi_params: dict, sample_params: dict, audio_params: dict):
    run = DEBUG_STORE.start()
    run.log("meta", "module_version", {"module": "parametrize_advanced_test", "version": "0.1.0"})
    run.log("run", "render_phase")
    run.log("run", "params_received", {"midi_keys": list(midi_params.keys()), "sample_keys": list(sample_params.keys()), "audio_keys": list(audio_params.keys())})
    run.log("func", "enter", {"module": "pipeline.py", "function": "run_render"})
    run.log("call", "generate_midi", {"module": "midi_engine.py"})
    midi_data = generate_midi(midi_params, run.log)
    pianoroll = generate_pianoroll(midi_data, run.log)
    run.log("call", "save_midi", {"module": "midi_engine.py"})
    midi_file = save_midi(midi_data, run.log)
    run.log("run", "midi_generated", {"has_file": bool(midi_file)})
    run.log("call", "select_samples", {"module": "sample_library.py"})
    sample_data = select_samples(sample_params, midi_data, run.log)
    run.log("run", "samples_selected", {"count": len(sample_data.get('samples', []))})
    run.log("call", "render_audio", {"module": "audio_renderer.py"})
    audio = render_audio(audio_params, midi_data, sample_data, run.log)
    run.log("run", "audio_rendered", {"audio_file": audio.get('audio_file')})
    run.log("run", "completed")
    run.log("func", "exit", {"module": "pipeline.py", "function": "run_render"})
    return {"run_id": run.run_id, "audio": audio, "midi_file": midi_file, "midi_image": pianoroll, "debug": DEBUG_STORE.get(run.run_id)}


def run_full(midi_params: dict, sample_params: dict, audio_params: dict):
    run = DEBUG_STORE.start()
    run.log("meta", "module_version", {"module": "parametrize_advanced_test", "version": "0.1.0"})
    run.log("run", "full_pipeline")
    run.log("run", "params_received", {"midi_keys": list(midi_params.keys()), "sample_keys": list(sample_params.keys()), "audio_keys": list(audio_params.keys())})
    run.log("func", "enter", {"module": "pipeline.py", "function": "run_full"})
    run.log("call", "generate_midi", {"module": "midi_engine.py"})
    midi_data = generate_midi(midi_params, run.log)
    pianoroll = generate_pianoroll(midi_data, run.log)
    run.log("call", "save_midi", {"module": "midi_engine.py"})
    midi_file = save_midi(midi_data, run.log)
    run.log("run", "midi_generated", {"has_file": bool(midi_file)})
    run.log("call", "select_samples", {"module": "sample_library.py"})
    sample_data = select_samples(sample_params, midi_data, run.log)
    run.log("run", "samples_selected", {"count": len(sample_data.get('samples', []))})
    run.log("call", "render_audio", {"module": "audio_renderer.py"})
    audio = render_audio(audio_params, midi_data, sample_data, run.log)
    run.log("run", "audio_rendered", {"audio_file": audio.get('audio_file')})
    run.log("run", "completed")
    run.log("func", "exit", {"module": "pipeline.py", "function": "run_full"})
    return {
        "run_id": run.run_id,
        "midi": midi_data,
        "samples": sample_data,
        "audio": audio,
        "midi_file": midi_file,
        "midi_image": pianoroll,
        "debug": DEBUG_STORE.get(run.run_id)
    }
