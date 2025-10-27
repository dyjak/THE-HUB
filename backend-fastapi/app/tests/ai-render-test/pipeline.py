from __future__ import annotations
from .debug_store import DEBUG_STORE
from .parameters import MidiParameters, AudioRenderParameters
from .chat_smoke.router import _midiify_core as ai_midiify
from .chat_smoke.router import ChatError as AIMidiError
from .local_library import discover_samples, select_local_sample, list_available_instruments, find_sample_by_id
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


def _summarize_configs(configs: list[dict]) -> list[dict]:
    summary: list[dict] = []
    for cfg in configs:
        if isinstance(cfg, dict):
            summary.append({
                "name": cfg.get("name"),
                "role": cfg.get("role"),
                "register": cfg.get("register"),
                "volume": cfg.get("volume"),
                "pan": cfg.get("pan"),
                "articulation": cfg.get("articulation"),
                "dynamic_range": cfg.get("dynamic_range"),
                "effects": cfg.get("effects", []),
            })
        else:  # graceful fallback for unexpected shapes
            summary.append({"name": getattr(cfg, "name", None)})
    return summary


def _log_midi_request(log_fn, midi_payload: dict):
    log_fn("params", "composition", {
        "style": midi_payload.get("style"),
        "mood": midi_payload.get("mood"),
        "tempo": midi_payload.get("tempo"),
        "key": midi_payload.get("key"),
        "scale": midi_payload.get("scale"),
        "meter": midi_payload.get("meter"),
        "bars": midi_payload.get("bars"),
        "length_seconds": midi_payload.get("length_seconds"),
        "dynamic_profile": midi_payload.get("dynamic_profile"),
        "arrangement_density": midi_payload.get("arrangement_density"),
        "harmonic_color": midi_payload.get("harmonic_color"),
        "form": midi_payload.get("form"),
    })
    log_fn("params", "instrumentarium", {
        "instruments": midi_payload.get("instruments", []),
        "configs": _summarize_configs(midi_payload.get("instrument_configs", [])),
    })


def _log_audio_request(log_fn, audio_payload: dict):
    log_fn("params", "audio_render", {
        "sample_rate": audio_payload.get("sample_rate"),
        "seconds": audio_payload.get("seconds"),
        "master_gain_db": audio_payload.get("master_gain_db"),
    })


def _compose_midi_via_ai(midi_payload: dict, run) -> dict:
    """Use the AI composer to generate MIDI JSON from parameters; ensure meta is populated."""
    provider = None; model = None
    try:
        # Allow run to carry last provider/model from previous logs if any; otherwise defaults in ai_midiify
        pass
    except Exception:
        pass
    midi_model = MidiParameters.from_dict(midi_payload)
    result = ai_midiify(midi_model, provider or "gemini", model, run=run)
    raw = result.get("raw")
    parsed = result.get("parsed")
    midi_data: dict
    if isinstance(parsed, dict):
        midi_data = parsed
    else:
        try:
            midi_data = json.loads(raw) if isinstance(raw, str) else {}
        except Exception:
            midi_data = {}
    if not isinstance(midi_data, dict):
        midi_data = {}
    # Enrich meta from payload
    meta = midi_data.setdefault('meta', {}) if isinstance(midi_data, dict) else {}
    for k in (
        'tempo','key','scale','style','mood','meter','form','dynamic_profile','arrangement_density','harmonic_color','length_seconds','bars','instrument_configs','seed'
    ):
        v = midi_payload.get(k)
        if v is not None:
            meta[k] = v
    meta.setdefault('instruments', midi_payload.get('instruments'))
    return midi_data


def run_midi(midi_params: dict, composer_provider: str | None = None, composer_model: str | None = None, ai_midi_data: dict | str | None = None):
    run = DEBUG_STORE.start()
    run.log("meta", "module_version", {"module": "ai_param_test", "version": "0.1.0"})
    run.log("run", "midi_phase")

    midi_model = MidiParameters.from_dict(midi_params)
    midi_payload = midi_model.to_dict()
    _log_midi_request(run.log, midi_payload)
    # AI-based composition replaces legacy engine; allow bypass with provided ai_midi_data
    if ai_midi_data is not None:
        if isinstance(ai_midi_data, dict):
            midi_data = ai_midi_data
        else:
            try:
                midi_data = json.loads(ai_midi_data)
            except Exception:
                midi_data = {}
        try:
            run.log("call", "ai_midiify", {"provider": composer_provider or "gemini", "model": composer_model or None, "bypass": True})
        except Exception:
            pass
    else:
        try:
            run.log("call", "ai_midiify", {"provider": composer_provider or "gemini", "model": composer_model or None})
        except Exception:
            pass
        try:
            ai_result = ai_midiify(MidiParameters.from_dict(midi_payload), (composer_provider or "gemini").lower(), composer_model, run=run)
            midi_data = ai_result.get("parsed")
            if not isinstance(midi_data, dict):
                raw = ai_result.get("raw")
                midi_data = json.loads(raw) if isinstance(raw, str) else {}
        except Exception:
            # Fallback wrapper to ensure structure
            midi_data = {}
    if not isinstance(midi_data, dict):
        midi_data = {}
    # enrich meta from payload
    meta = midi_data.setdefault('meta', {})
    meta.setdefault('tempo', midi_payload.get('tempo'))
    meta.setdefault('key', midi_payload.get('key'))
    meta.setdefault('scale', midi_payload.get('scale'))
    meta['style'] = midi_payload.get('style')
    meta['mood'] = midi_payload.get('mood')
    meta['meter'] = midi_payload.get('meter')
    meta['form'] = midi_payload.get('form')
    meta['dynamic_profile'] = midi_payload.get('dynamic_profile')
    meta['arrangement_density'] = midi_payload.get('arrangement_density')
    meta['harmonic_color'] = midi_payload.get('harmonic_color')
    meta['length_seconds'] = midi_payload.get('length_seconds')
    meta['bars'] = midi_payload.get('bars')
    meta['instrument_configs'] = midi_payload.get('instrument_configs')
    meta['seed'] = midi_payload.get('seed')
    meta.setdefault('instruments', midi_payload.get('instruments'))

    meta = midi_data.setdefault('meta', {})
    meta.setdefault('tempo', midi_payload.get('tempo'))
    meta.setdefault('key', midi_payload.get('key'))
    meta.setdefault('scale', midi_payload.get('scale'))
    meta['style'] = midi_payload.get('style')
    meta['mood'] = midi_payload.get('mood')
    meta['meter'] = midi_payload.get('meter')
    meta['form'] = midi_payload.get('form')
    meta['dynamic_profile'] = midi_payload.get('dynamic_profile')
    meta['arrangement_density'] = midi_payload.get('arrangement_density')
    meta['harmonic_color'] = midi_payload.get('harmonic_color')
    meta['length_seconds'] = midi_payload.get('length_seconds')
    meta['bars'] = midi_payload.get('bars')
    meta['instrument_configs'] = midi_payload.get('instrument_configs')
    meta['seed'] = midi_payload.get('seed')
    meta.setdefault('instruments', midi_payload.get('instruments'))
    run.log("run", "midi_generated", {"bars": len(midi_data.get('pattern', [])), "instruments": meta.get('instruments') or midi_payload.get('instruments')})
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
    # Helpers for MIDI export
    def _export_pattern_to_mid(pattern: list[dict], tempo_bpm: int, out_path: Path) -> Path | None:
        if mido is None:
            return None
        mid = mido.MidiFile()
        track = mido.MidiTrack()
        mid.tracks.append(track)
        mpb = int(60_000_000 / max(1, tempo_bpm))
        track.append(mido.MetaMessage('set_tempo', tempo=mpb, time=0))
        ticks_per_beat = mid.ticks_per_beat  # default 480
        step_ticks = int(ticks_per_beat * 0.5)  # 8 steps/bar -> 0.5 beat per step (4/4)
        flat: list[tuple[int,bool,int,int]] = []
        for bar in pattern:
            b_index = bar.get('bar', 0)
            for ev in bar.get('events', []):
                note = ev.get('note', 60)
                vel = ev.get('vel', 64)
                step = ev.get('step', 0)
                start_tick = (b_index * 8 + step) * step_ticks
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
        mid.save(str(out_path))
        return out_path

    # Real MIDI export (combined + per layer)
    midi_file_path = None
    midi_layer_paths: dict[str, str] = {}
    if mido is not None:
        try:
            tempo_bpm = midi_data.get('meta', {}).get('tempo', 80)
            # Combined
            midi_file_path = _export_pattern_to_mid(midi_data.get('pattern', []), tempo_bpm, run_dir / "midi.mid")
            if midi_file_path:
                run.log("midi", "export_mid", {"file": str(midi_file_path)})
            # Per-instrument layers
            layers: dict = midi_data.get('layers', {}) or {}
            for inst, pat in layers.items():
                try:
                    p = _export_pattern_to_mid(pat, tempo_bpm, run_dir / f"midi_{inst}.mid")
                    if p:
                        midi_layer_paths[inst] = str(p)
                        run.log("midi", "export_mid_layer", {"instrument": inst, "file": str(p)})
                except Exception as e:
                    run.log("midi", "export_mid_layer_failed", {"instrument": inst, "error": str(e)})
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
               "midi_mid_layers": midi_layer_paths if midi_layer_paths else None,
               "midi_mid_layers_rel": {k: _rel(Path(v)) for k, v in midi_layer_paths.items()} if midi_layer_paths else None,
               "midi_image": None,
               "blueprint": {"midi": midi_payload},
               "debug": DEBUG_STORE.get(run.run_id)}
    if viz and 'combined' in viz:
        img_path = Path(viz['combined'])
        payload['midi_image'] = {"combined": str(img_path), "combined_rel": _rel(img_path)}
        # Per-instrument pianorolls
        layers_viz = viz.get('layers') if isinstance(viz, dict) else None
        if isinstance(layers_viz, dict) and layers_viz:
            payload['midi_image_layers'] = {k: str(v) for k, v in layers_viz.items()}
            payload['midi_image_layers_rel'] = {k: _rel(Path(v)) for k, v in layers_viz.items()}
            run.log("viz", "pianoroll_layers_present", {"count": len(layers_viz)})
        # Per-instrument pianorolls
        layers_viz = viz.get('layers') if isinstance(viz, dict) else None
        if isinstance(layers_viz, dict) and layers_viz:
            payload['midi_image_layers'] = {k: str(v) for k, v in layers_viz.items()}
            payload['midi_image_layers_rel'] = {k: _rel(Path(v)) for k, v in layers_viz.items()}
    return payload


def _prepare_local_samples(instruments: list[str], run_log, selected_samples: dict[str, str] | None = None):
    library = discover_samples()
    run_log("samples", "library_indexed", {"instruments_indexed": len(library), "available": list_available_instruments(library)})
    selected = []
    for idx, inst in enumerate(instruments):
        s = None
        # If user provided a specific sample id for this instrument, prefer it
        if selected_samples and inst in selected_samples:
            try:
                s = find_sample_by_id(library, inst, str(selected_samples[inst]))
                if s:
                    run_log("samples", "instrument_sample_overridden", {"instrument": inst, "id": s.id, "file": str(s.file)})
            except Exception:
                s = None
        if s is None:
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


def run_render(midi_params: dict, audio_params: dict, selected_samples: dict[str, str] | None = None, composer_provider: str | None = None, composer_model: str | None = None, ai_midi_data: dict | str | None = None):
    run = DEBUG_STORE.start()
    run.log("meta", "module_version", {"module": "ai_param_test", "version": "0.1.0"})
    run.log("run", "render_phase")
    midi_model = MidiParameters.from_dict(midi_params)
    audio_model = AudioRenderParameters.from_dict(audio_params)
    midi_payload = midi_model.to_dict()
    audio_payload = audio_model.to_dict()

    _log_midi_request(run.log, midi_payload)
    _log_audio_request(run.log, audio_payload)

    # Use provided AI MIDI if present, otherwise compose via AI
    if ai_midi_data is not None:
        if isinstance(ai_midi_data, dict):
            midi_data = ai_midi_data
        else:
            try:
                midi_data = json.loads(ai_midi_data)
            except Exception:
                midi_data = {}
        try:
            run.log("call", "ai_midiify", {"provider": composer_provider or "gemini", "model": composer_model or None, "bypass": True})
        except Exception:
            pass
    else:
        try:
            run.log("call", "ai_midiify", {"provider": composer_provider or "gemini", "model": composer_model or None})
        except Exception:
            pass
        try:
            ai_result = ai_midiify(MidiParameters.from_dict(midi_payload), (composer_provider or "gemini").lower(), composer_model, run=run)
            midi_data = ai_result.get("parsed")
            if not isinstance(midi_data, dict):
                raw = ai_result.get("raw")
                midi_data = json.loads(raw) if isinstance(raw, str) else {}
        except Exception:
            midi_data = {}
    if not isinstance(midi_data, dict):
        midi_data = {}

    meta = midi_data.setdefault('meta', {})
    meta.setdefault('tempo', midi_payload.get('tempo'))
    meta.setdefault('key', midi_payload.get('key'))
    meta.setdefault('scale', midi_payload.get('scale'))
    meta['style'] = midi_payload.get('style')
    meta['mood'] = midi_payload.get('mood')
    meta['meter'] = midi_payload.get('meter')
    meta['form'] = midi_payload.get('form')
    meta['dynamic_profile'] = midi_payload.get('dynamic_profile')
    meta['arrangement_density'] = midi_payload.get('arrangement_density')
    meta['harmonic_color'] = midi_payload.get('harmonic_color')
    meta['length_seconds'] = midi_payload.get('length_seconds')
    meta['bars'] = midi_payload.get('bars')
    meta['instrument_configs'] = midi_payload.get('instrument_configs')
    meta['seed'] = midi_payload.get('seed')
    meta.setdefault('instruments', midi_payload.get('instruments'))

    instruments = meta.get('instruments') or []
    # Safety: normalize and auto-filter instruments to those available in local library
    try:
        lib = discover_samples()
        available = set(list_available_instruments(lib))
        # Alias/fallbacks (mirror router logic)
        alias_fallbacks = {
            "strings_ensemble": ["strings", "pad"],
            "string_ensemble": ["strings", "pad"],
            "stringsensemble": ["strings", "pad"],
            "orchestral_strings": ["strings", "pad"],
            "french_horn": ["lead", "misc"],
            "horn": ["lead", "misc"],
            "timpani": ["tom", "kick", "perc"],
        }
        if 'drums' in instruments:
            # Expand virtual 'drums' to available drum components
            drum_components = ["kick", "snare", "hihat", "clap", "808"]
            expanded: list[str] = []
            for inst in instruments:
                if inst == 'drums':
                    expanded.extend([d for d in drum_components if d in available])
                else:
                    expanded.append(inst)
            instruments = expanded
        # Substitute aliases
        subs: dict[str, str] = {}
        normalized: list[str] = []
        for inst in instruments:
            key = str(inst).strip().lower().replace(" ", "_")
            if inst in available:
                normalized.append(inst)
                continue
            cands = alias_fallbacks.get(key, [])
            chosen = None
            for c in cands:
                if c in available:
                    chosen = c; break
            if chosen:
                subs[inst] = chosen
                normalized.append(chosen)
            else:
                normalized.append(inst)
        filtered = [i for i in normalized if i in available]
        if filtered != instruments:
            run.log("samples", "instruments_filtered", {"before": instruments, "after": filtered, "available": sorted(available)})
            instruments = filtered
            # Apply layer substitutions then prune to filtered set
            try:
                layers = midi_data.get('layers') or {}
                # migrate old->new if substitution occurred
                for old, new in subs.items():
                    if old in layers and new not in layers:
                        layers[new] = layers.pop(old)
                    elif old in layers and new in layers:
                        # merge events if both exist
                        try:
                            # naive merge by bar index
                            by_bar = {}
                            for bar in layers[new]:
                                by_bar[bar.get('bar', 0)] = bar
                            for bar in layers[old]:
                                b = bar.get('bar', 0)
                                dst = by_bar.setdefault(b, {"bar": b, "events": []})
                                dst.setdefault('events', []).extend(bar.get('events', []))
                            layers.pop(old, None)
                            layers[new] = [by_bar[b] for b in sorted(by_bar.keys())]
                        except Exception:
                            layers.pop(old, None)
                midi_data['layers'] = {k: v for k, v in layers.items() if k in set(instruments)}
            except Exception:
                pass
            meta['instruments'] = instruments
            if subs:
                try:
                    meta['instrument_substitutions'] = subs
                except Exception:
                    pass
    except Exception as e:
        # Non-fatal: continue with original instruments if discovery fails
        run.log("samples", "filter_failed", {"error": str(e)})

    run.log("call", "prepare_local_samples", {"count": len(instruments)})
    samples = _prepare_local_samples(instruments, run.log, selected_samples=selected_samples)
    if len(samples.get("samples", [])) != len(instruments):
        have = [s['instrument'] for s in samples['samples']]
        missing = [i for i in instruments if i not in have]
        run.log("samples", "missing_optional", {"expected": instruments, "have": have, "missing": missing})
        # Proceed with the samples we have by updating instruments/meta accordingly
        instruments = have
        meta['instruments'] = instruments
    # Prepare per-run directory before rendering audio
    base_out = Path(__file__).parent / "output"
    base_out.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    run_dir = base_out / f"{ts}_{run.run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)
    run.log("call", "render_audio", {"run_dir": str(run_dir)})
    try:
        audio = render_audio(audio_payload, midi_data, samples, run.log, run.run_id, run_dir=run_dir)
    except SampleMissingError as e:
        run.log("audio", "render_failed", {"error": str(e)})
        run.log("run", "failed", {"reason": "audio", "error": str(e)})
        raise
    except Exception as e:
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
                "instrument_configs": midi_payload.get('instrument_configs'),
                "form": midi_payload.get('form'),
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
    result = {
        "run_id": run.run_id,
        "midi": midi_data,
        "samples": samples,
        "audio": audio,
        "blueprint": {"midi": midi_payload, "audio": audio_payload},
        "debug": DEBUG_STORE.get(run.run_id)
    }
    # Add midi export info if run_midi logic reused here -> combined + per-layer export
    try:
        if mido is not None:
            tempo_bpm = midi_data.get('meta', {}).get('tempo', 80)
            # Ensure JSON snapshot
            track_json = run_dir / "midi.json"
            try:
                with track_json.open('w', encoding='utf-8') as f:
                    json.dump(midi_data, f)
                result['midi_json'] = str(track_json)
                result['midi_json_rel'] = _rel(track_json)
                run.log("midi", "json_saved", {"file": str(track_json)})
            except Exception:
                pass
            # Combined export
            def _export_pattern_to_mid(pattern: list[dict], tempo_bpm: int, out_path: Path) -> Path | None:
                mid = mido.MidiFile()
                track = mido.MidiTrack(); mid.tracks.append(track)
                mpb = int(60_000_000 / max(1, tempo_bpm))
                track.append(mido.MetaMessage('set_tempo', tempo=mpb, time=0))
                ticks_per_beat = mid.ticks_per_beat; step_ticks = int(ticks_per_beat * 0.5)
                flat: list[tuple[int,bool,int,int]] = []
                for bar in pattern:
                    b_index = bar.get('bar', 0)
                    for ev in bar.get('events', []):
                        note = ev.get('note', 60); vel = ev.get('vel', 64); step = ev.get('step', 0)
                        start_tick = (b_index * 8 + step) * step_ticks
                        length_steps = ev.get('len', 1); end_tick = start_tick + length_steps * step_ticks
                        flat.append((start_tick, True, note, vel)); flat.append((end_tick, False, note, vel))
                flat.sort(key=lambda x: x[0])
                current_tick = 0
                for tick, is_on, note, vel in flat:
                    delta = tick - current_tick; current_tick = tick
                    if is_on:
                        track.append(mido.Message('note_on', note=note, velocity=vel, time=delta))
                    else:
                        track.append(mido.Message('note_off', note=note, velocity=0, time=delta))
                mid.save(str(out_path)); return out_path
            track_path = _export_pattern_to_mid(midi_data.get('pattern', []), tempo_bpm, run_dir / "midi.mid")
            if track_path:
                result['midi_mid'] = str(track_path)
                result['midi_mid_rel'] = _rel(track_path)
                run.log("midi", "export_mid", {"file": str(track_path)})
            # Per-layer exports
            layer_map: dict[str, str] = {}
            for inst, pat in (midi_data.get('layers', {}) or {}).items():
                try:
                    p = _export_pattern_to_mid(pat, tempo_bpm, run_dir / f"midi_{inst}.mid")
                    if p:
                        layer_map[inst] = str(p)
                        run.log("midi", "export_mid_layer", {"instrument": inst, "file": str(p)})
                except Exception:
                    continue
            if layer_map:
                result['midi_mid_layers'] = layer_map
                result['midi_mid_layers_rel'] = {k: _rel(Path(v)) for k, v in layer_map.items()}
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
    # Add per-instrument pianorolls (relative) if present
    if isinstance(viz, dict) and isinstance(viz.get('layers'), dict) and viz['layers']:
        result['midi_image_layers'] = viz['layers']
        try:
            result['midi_image_layers_rel'] = {k: _rel(Path(v)) for k, v in viz['layers'].items()}
        except Exception:
            pass
        run.log("viz", "pianoroll_layers_present", {"count": len(viz['layers'])})
    # Audio stems summary if present
    if isinstance(audio, dict) and isinstance(audio.get('stems_rel'), dict):
        try:
            run.log("audio", "stems_present", {"count": len(audio['stems_rel']), "instruments": list(audio['stems_rel'].keys())})
        except Exception:
            pass
    return result


def run_full(midi_params: dict, audio_params: dict, selected_samples: dict[str, str] | None = None, composer_provider: str | None = None, composer_model: str | None = None):
    # For this simplified module, run_full == run_render
    return run_render(midi_params, audio_params, selected_samples=selected_samples, composer_provider=composer_provider, composer_model=composer_model)
