from __future__ import annotations
from typing import Dict, Any, List
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


def generate_midi(params: Dict[str, Any], log):
    log("func", "enter", {"module": "midi_engine.py", "function": "generate_midi", "params_keys": list(params.keys())})
    seed = params.get("seed")
    if seed is not None:
        random.seed(seed)
        log("midi", "seed_initialized", {"seed": seed})
    key = params.get("key", "C")
    scale = params.get("scale", "major")
    scale_key = f"{key}_{scale}"
    notes = SCALE_NOTES.get(scale_key, SCALE_NOTES["C_major"])
    bars = params.get("bars", 8)
    tempo = params.get("tempo", 80)
    instruments = params.get("instruments", [])

    log("midi", "init", {"bars": bars, "tempo": tempo, "instruments": instruments})
    log("midi", "scale_resolved", {"scale_key": scale_key, "note_pool_size": len(notes)})

    pattern: List[Dict[str, Any]] = []
    for bar in range(bars):
        bar_events = []
        for step in range(8):
            if random.random() < 0.7:
                note = random.choice(notes)
                velocity = random.randint(50, 100)
                bar_events.append({"step": step, "note": note, "vel": velocity, "len": 1})
        log("midi", "bar_composed", {"bar": bar, "events": len(bar_events)})
        pattern.append({"bar": bar, "events": bar_events})
    log("midi", "pattern_generated", {"total_bars": bars, "non_empty": sum(1 for b in pattern if b['events'])})
    total_events = sum(len(b["events"]) for b in pattern)
    log("midi", "pattern_stats", {"total_events": total_events, "avg_events_per_bar": total_events / max(1, bars)})

    result = {"pattern": pattern, "meta": {"tempo": tempo, "instruments": instruments}}
    log("func", "exit", {"module": "midi_engine.py", "function": "generate_midi", "pattern_bars": len(pattern)})
    return result


def save_midi(midi_data: Dict[str, Any], log) -> str | None:
    log("func", "enter", {"module": "midi_engine.py", "function": "save_midi", "pattern_bars": len(midi_data.get("pattern", []))})
    """Zapisuje wygenerowany pattern do pliku MIDI (prosty mapping). Jeśli brak mido – zwraca None."""
    if mido is None:
        log("midi", "mido_missing", {"info": "mido not installed - skipping midi file save"})
        return None
    pattern = midi_data.get("pattern", [])
    tempo = midi_data.get("meta", {}).get("tempo", 80)
    ticks_per_beat = 480
    mid = mido.MidiFile(ticks_per_beat=ticks_per_beat)
    track = mido.MidiTrack()
    mid.tracks.append(track)

    # tempo meta (convert BPM to microseconds per beat)
    mpqn = int(60_000_000 / max(1, tempo))
    log("midi", "tempo_meta", {"bpm": tempo, "mpqn": mpqn})
    track.append(mido.MetaMessage('set_tempo', tempo=mpqn, time=0))

    # naive mapping: each bar has 8 steps -> quarter notes subdivisions
    step_ticks = ticks_per_beat // 2  # 8 steps per bar => (4 beats * ticks)/8 = ticks/2
    msg_count = 0
    for bar in pattern:
        for event in bar.get("events", []):
            note = event["note"]
            velocity = event["vel"]
            track.append(mido.Message('note_on', note=note, velocity=velocity, time=0))
            # length 1 step
            track.append(mido.Message('note_off', note=note, velocity=0, time=step_ticks))
            msg_count += 2
        log("midi", "bar_serialized", {"bar": bar.get("bar"), "events": len(bar.get("events", [])), "messages": msg_count})
        # bar padding: ensure bar length uniform (8 steps * step_ticks)
        track.append(mido.MetaMessage('marker', text=f"bar_end", time=0))

    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True, parents=True)
    midi_path = output_dir / "pattern.mid"
    mid.save(str(midi_path))
    size = midi_path.stat().st_size if midi_path.exists() else 0
    log("midi", "midi_file_saved", {"file": str(midi_path), "bytes": size, "messages": msg_count})
    log("func", "exit", {"module": "midi_engine.py", "function": "save_midi", "file": str(midi_path)})
    return str(midi_path)
