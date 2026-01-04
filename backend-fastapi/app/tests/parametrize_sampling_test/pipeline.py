from __future__ import annotations
from .debug_store import DEBUG_STORE
from .parameters import MidiParameters, AudioRenderParameters
from .midi_engine import generate_midi
from .local_library import discover_samples, select_local_sample, list_available_instruments
from .audio_renderer import render_audio, SampleMissingError
from .midi_visualizer import render_pianoroll
from pathlib import Path
import json, time
from datetime import datetime
try:
    import mido  # type: ignore
except Exception:
    mido = None  # type: ignore


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
    base_out = Path(__file__).parent / "output"
    base_out.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    run_dir = base_out / f"{ts}_{run.run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)
    midi_path = run_dir / "midi.json"
    try:
        with midi_path.open('w', encoding='utf-8') as f:
            json.dump(midi_data, f)
        run.log("midi", "saved", {"file": str(midi_path)})
    except Exception as e:
        run.log("midi", "save_failed", {"error": str(e)})
    # Real MIDI export (single combined track) if mido available
    midi_file_path = None
    if mido is not None:
        try:
            mid = mido.MidiFile()
            track = mido.MidiTrack()
            mid.tracks.append(track)
            tempo_bpm = midi_data.get('meta', {}).get('tempo', 80)
            # mido tempo is microseconds per beat
            mpb = int(60_000_000 / max(1, tempo_bpm))
            track.append(mido.MetaMessage('set_tempo', tempo=mpb, time=0))
            ticks_per_beat = mid.ticks_per_beat  # default 480
            step_div = 8  # we used 8 steps per bar
            # duration of one bar in beats = 4 (assuming 4/4)
            # one step -> 4 beats / 8 = 0.5 beat
            step_ticks = int(ticks_per_beat * 0.5)
            for bar in midi_data.get('pattern', []):
                b_index = bar.get('bar', 0)
                for ev in bar.get('events', []):
                    note = ev.get('note', 60)
                    vel = ev.get('vel', 64)
                    step = ev.get('step', 0)
                    start_tick = (b_index * step_div + step) * step_ticks
                    # Insert time deltas: ensure events sorted
                    # We'll accumulate events then sort
            # Build flattened events list
            flat = []
            for bar in midi_data.get('pattern', []):
                b_index = bar.get('bar', 0)
                for ev in bar.get('events', []):
                    note = ev.get('note', 60)
                    vel = ev.get('vel', 64)
                    step = ev.get('step', 0)
                    start_tick = (b_index * step_div + step) * step_ticks
                    length_steps = ev.get('len', 1)
                    end_tick = start_tick + length_steps * step_ticks
                    flat.append((start_tick, True, note, vel))
                    flat.append((end_tick, False, note, vel))
            flat.sort(key=lambda x: x[0])
            current_tick = 0
            for tick, is_on, note, vel in flat:
                delta = tick - current_tick
                current_tick = tick
                if is_on:
                    track.append(mido.Message('note_on', note=note, velocity=vel, time=delta))
                else:
                    track.append(mido.Message('note_off', note=note, velocity=0, time=delta))
            midi_file_path = run_dir / "midi.mid"
            mid.save(str(midi_file_path))
            run.log("midi", "export_mid", {"file": str(midi_file_path)})
        except Exception as e:
            run.log("midi", "export_mid_failed", {"error": str(e)})
    # Visualization
    viz = render_pianoroll(midi_data, run_dir, run.run_id, run.log)
    # relative helpers
    def _rel(p: Path | None):
        if p is None: return None
        try:
            return str(p.relative_to(base_out))
        except Exception:
            return p.name
    run.log("run", "completed")
    payload = {"run_id": run.run_id, "midi": midi_data,
               "midi_json": str(midi_path), "midi_json_rel": _rel(midi_path),
               "midi_mid": str(midi_file_path) if midi_file_path else None,
               "midi_mid_rel": _rel(midi_file_path) if midi_file_path else None,
               "midi_image": None, "debug": DEBUG_STORE.get(run.run_id)}
    if viz and 'combined' in viz:
        img_path = Path(viz['combined'])
        payload['midi_image'] = {"combined": str(img_path), "combined_rel": _rel(img_path)}
    return payload


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
                "subtype": getattr(s, 'subtype', None),
                "family": getattr(s, 'family', None),
                "category": getattr(s, 'category', None),
                "pitch": getattr(s, 'pitch', None),
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
    # Prepare per-run directory before rendering audio
    base_out = Path(__file__).parent / "output"
    base_out.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    run_dir = base_out / f"{ts}_{run.run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)
    run.log("call", "render_audio", {"run_dir": str(run_dir)})
    try:
        audio = render_audio(audio_params, midi_data, samples, run.log, run.run_id, run_dir=run_dir)
    except SampleMissingError as e:
        run.log("audio", "render_failed", {"error": str(e)})
        run.log("run", "failed", {"reason": "audio", "error": str(e)})
        raise
    # Write selection snapshot for reproducibility
    try:
        selection_path = run_dir / "selection.json"
        with selection_path.open('w', encoding='utf-8') as f:
            json.dump({
                "run_id": run.run_id,
                "instruments": instruments,
                "samples": samples.get('samples', []),
            }, f, indent=2)
        run.log("samples", "selection_snapshot_saved", {"file": str(selection_path)})
    except Exception as e:
        run.log("samples", "selection_snapshot_failed", {"error": str(e)})
    # Visualization after audio (or before, order not critical)
    viz = render_pianoroll(midi_data, run_dir, run.run_id, run.log)
    run.log("run", "audio_rendered", {"file": audio.get('audio_file')})
    run.log("run", "completed")
    def _rel(p: Path | None):
        if p is None: return None
        try:
            return str(p.relative_to(base_out))
        except Exception:
            return p.name
    # Merge audio relative path if provided
    if 'audio_file' in audio:
        try:
            af = Path(audio['audio_file'])
            audio['audio_file_rel'] = _rel(af)
        except Exception:
            pass
    result = {"run_id": run.run_id, "midi": midi_data, "samples": samples, "audio": audio, "debug": DEBUG_STORE.get(run.run_id)}
    # Add midi export info if run_midi logic reused here -> replicate minimal export for convenience
    try:
        # reuse run_dir/ts already defined above
        if mido is not None:
            mid = mido.MidiFile(); track = mido.MidiTrack(); mid.tracks.append(track)
            tempo_bpm = midi_data.get('meta', {}).get('tempo', 80)
            mpb = int(60_000_000 / max(1, tempo_bpm))
            track.append(mido.MetaMessage('set_tempo', tempo=mpb, time=0))
            ticks_per_beat = mid.ticks_per_beat
            step_div = 8; step_ticks = int(ticks_per_beat * 0.5)
            flat = []
            for bar in midi_data.get('pattern', []):
                b_index = bar.get('bar', 0)
                for ev in bar.get('events', []):
                    note = ev.get('note', 60); vel = ev.get('vel', 64); step = ev.get('step', 0)
                    start_tick = (b_index * step_div + step) * step_ticks
                    length_steps = ev.get('len', 1)
                    end_tick = start_tick + length_steps * step_ticks
                    flat.append((start_tick, True, note, vel))
                    flat.append((end_tick, False, note, vel))
            flat.sort(key=lambda x: x[0])
            current_tick = 0
            track_path = run_dir / "midi.mid"
            track_json = run_dir / "midi.json"
            # Write JSON pattern (overwrite okay)
            try:
                with track_json.open('w', encoding='utf-8') as f:
                    json.dump(midi_data, f)
            except Exception:
                pass
            for tick, is_on, note, vel in flat:
                delta = tick - current_tick; current_tick = tick
                if is_on:
                    track.append(mido.Message('note_on', note=note, velocity=vel, time=delta))
                else:
                    track.append(mido.Message('note_off', note=note, velocity=0, time=delta))
            mid.save(str(track_path))
            result['midi_mid'] = str(track_path)
            result['midi_json'] = str(track_json)
            result['midi_mid_rel'] = _rel(track_path)
            result['midi_json_rel'] = _rel(track_json)
    except Exception as e:  # pragma: no cover simple safety
        run.log("midi", "inline_export_failed", {"error": str(e)})
    if 'midi_json' not in result or 'midi_mid' not in result:
        # Ensure reference to previously exported within this run
        # (If missing because of earlier failure, ignore silently)
        pass
    if viz and 'combined' in viz:
        img_path = Path(viz['combined'])
        result['midi_image'] = {"combined": str(img_path), "combined_rel": _rel(img_path)}
    else:
        result['midi_image'] = viz
    return result


def run_full(midi_params: dict, audio_params: dict):
    # For this simplified module, run_full == run_render
    return run_render(midi_params, audio_params)
