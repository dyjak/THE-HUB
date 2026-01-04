from __future__ import annotations
from typing import Dict, Any, List, Tuple
from pathlib import Path
try:
    import mido
except ImportError:  # fallback jeśli brak zależności
    mido = None  # type: ignore
import random

SCALE_NOTES = {
    "C_major": [60, 62, 64, 65, 67, 69, 71],
    "A_minor": [57, 59, 60, 62, 64, 65, 67],
    "F_major": [65, 67, 69, 70, 72, 74, 76],
}


def _compose_single_layer(notes: List[int], bars: int, rng: random.Random, log, layer_name: str) -> List[Dict[str, Any]]:
    pattern: List[Dict[str, Any]] = []
    for bar in range(bars):
        bar_events = []
        for step in range(8):
            if rng.random() < 0.7:
                note = rng.choice(notes)
                velocity = rng.randint(50, 100)
                bar_events.append({"step": step, "note": note, "vel": velocity, "len": 1})
        log("midi", "bar_composed", {"bar": bar, "events": len(bar_events), "layer": layer_name})
        pattern.append({"bar": bar, "events": bar_events})
    return pattern


def generate_midi(params: Dict[str, Any], log):
    log("func", "enter", {"module": "midi_engine.py", "function": "generate_midi", "params_keys": list(params.keys())})
    seed = params.get("seed")
    rng = random.Random(seed)
    if seed is not None:
        log("midi", "seed_initialized", {"seed": seed})
    key = params.get("key", "C")
    scale = params.get("scale", "major")
    scale_key = f"{key}_{scale}"
    notes = SCALE_NOTES.get(scale_key, SCALE_NOTES["C_major"])
    bars = params.get("bars", 8)
    tempo = params.get("tempo", 80)
    instruments: List[str] = params.get("instruments", []) or ["piano"]

    log("midi", "init", {"bars": bars, "tempo": tempo, "instruments": instruments})
    log("midi", "scale_resolved", {"scale_key": scale_key, "note_pool_size": len(notes)})

    # Warstwowa generacja: osobny pattern per instrument
    layers: Dict[str, List[Dict[str, Any]]] = {}
    combined_pattern: List[Dict[str, Any]] = [{"bar": b, "events": []} for b in range(bars)]

    for inst in instruments:
        log("midi", "layer_start", {"instrument": inst})
        layer_pattern = _compose_single_layer(notes, bars, rng, log, inst)
        layers[inst] = layer_pattern
        # Merge do combined
        for b in range(bars):
            combined_pattern[b]["events"].extend(layer_pattern[b]["events"])
        non_empty = sum(1 for b in layer_pattern if b['events'])
        total_events = sum(len(b["events"]) for b in layer_pattern)
        log("midi", "layer_done", {"instrument": inst, "bars": bars, "non_empty": non_empty, "events": total_events})

    # Statystyki combined
    log("midi", "pattern_generated", {"total_bars": bars, "non_empty": sum(1 for b in combined_pattern if b['events']), "layers": len(layers)})
    total_events = sum(len(b["events"]) for b in combined_pattern)
    log("midi", "pattern_stats", {"total_events": total_events, "avg_events_per_bar": total_events / max(1, bars)})

    result = {
        "pattern": combined_pattern,
        "layers": layers,
        "meta": {"tempo": tempo, "instruments": instruments}
    }
    log("func", "exit", {"module": "midi_engine.py", "function": "generate_midi", "pattern_bars": len(combined_pattern), "layers": list(layers.keys())})
    return result


def _write_midi_file(pattern: List[Dict[str, Any]], tempo: int, output_path: Path, log) -> Tuple[str, int]:
    ticks_per_beat = 480
    mid = mido.MidiFile(ticks_per_beat=ticks_per_beat)
    track = mido.MidiTrack()
    mid.tracks.append(track)

    mpqn = int(60_000_000 / max(1, tempo))
    log("midi", "tempo_meta", {"bpm": tempo, "mpqn": mpqn, "file": str(output_path)})
    track.append(mido.MetaMessage('set_tempo', tempo=mpqn, time=0))

    step_ticks = ticks_per_beat // 2
    msg_count = 0
    for bar in pattern:
        for event in bar.get("events", []):
            note = event["note"]
            velocity = event["vel"]
            track.append(mido.Message('note_on', note=note, velocity=velocity, time=0))
            track.append(mido.Message('note_off', note=note, velocity=0, time=step_ticks))
            msg_count += 2
        log("midi", "bar_serialized", {"bar": bar.get("bar"), "events": len(bar.get("events", [])), "messages": msg_count, "file": str(output_path)})
        track.append(mido.MetaMessage('marker', text=f"bar_end", time=0))

    mid.save(str(output_path))
    size = output_path.stat().st_size if output_path.exists() else 0
    log("midi", "midi_file_saved", {"file": str(output_path), "bytes": size, "messages": msg_count})
    return str(output_path), msg_count


def save_midi(midi_data: Dict[str, Any], log) -> str | Dict[str, str] | None:
    log("func", "enter", {"module": "midi_engine.py", "function": "save_midi", "pattern_bars": len(midi_data.get("pattern", []))})
    """Zapisuje wygenerowany pattern do pliku MIDI (łącznie) oraz per instrument (jeśli dostępne). Jeśli brak mido – zwraca None."""
    if mido is None:
        log("midi", "mido_missing", {"info": "mido not installed - skipping midi file save"})
        return None

    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True, parents=True)

    tempo = midi_data.get("meta", {}).get("tempo", 80)
    combined_pattern = midi_data.get("pattern", [])
    layers: Dict[str, List[Dict[str, Any]]] = midi_data.get("layers", {})

    # Zapis pliku łącznego
    combined_path = output_dir / "pattern.mid"
    combined_file, combined_msgs = _write_midi_file(combined_pattern, tempo, combined_path, log)

    # Zapis plików per instrument
    per_instrument_files: Dict[str, str] = {}
    for inst, pat in layers.items():
        inst_path = output_dir / f"pattern_{inst}.mid"
        f, _ = _write_midi_file(pat, tempo, inst_path, log)
        per_instrument_files[inst] = f

    log("func", "exit", {"module": "midi_engine.py", "function": "save_midi", "file": combined_file, "per_instrument": list(per_instrument_files.keys())})
    return {"combined": combined_file, "layers": per_instrument_files}
