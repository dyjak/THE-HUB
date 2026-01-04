from __future__ import annotations
from typing import Dict, Any, List
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
    log("func", "enter", {"module": "midi_engine", "function": "generate_midi"})
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
    layers: Dict[str, List[Dict[str, Any]]] = {}
    combined: List[Dict[str, Any]] = [{"bar": b, "events": []} for b in range(bars)]
    for inst in instruments:
        layer = _compose_single_layer(notes, bars, rng, log, inst)
        layers[inst] = layer
        for b in range(bars):
            combined[b]["events"].extend(layer[b]["events"])
    result = {"pattern": combined, "layers": layers, "meta": {"tempo": tempo, "instruments": instruments}}
    log("func", "exit", {"module": "midi_engine", "function": "generate_midi"})
    return result
