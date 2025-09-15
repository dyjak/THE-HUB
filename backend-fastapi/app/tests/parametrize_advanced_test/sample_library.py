from __future__ import annotations
from typing import Dict, Any, List
import random

SAMPLE_POOL = [
    {"id": "pad_warm", "type": "pad", "organic": False},
    {"id": "pad_analog", "type": "pad", "organic": True},
    {"id": "piano_grand", "type": "piano", "organic": True},
    {"id": "piano_ep", "type": "piano", "organic": False},
    {"id": "drum_kick_soft", "type": "drums", "organic": False},
    {"id": "drum_snare_vintage", "type": "drums", "organic": True},
]


def select_samples(params: Dict[str, Any], midi_data: Dict[str, Any], log):
    log("func", "enter", {"module": "sample_library.py", "function": "select_samples", "params_keys": list(params.keys()), "midi_has_pattern": "pattern" in midi_data})
    layers = params.get("layers", 3)
    prefer_organic = params.get("prefer_organic", True)
    add_percussion = params.get("add_percussion", True)

    log("samples", "selection_start", {"layers": layers, "prefer_organic": prefer_organic, "total_pool": len(SAMPLE_POOL)})

    chosen: List[Dict[str, Any]] = []
    pool = SAMPLE_POOL.copy()
    random.shuffle(pool)
    rejected = 0
    for sample in pool:
        if len(chosen) >= layers:
            break
        if prefer_organic and not sample["organic"]:
            rejected += 1
            continue
        chosen.append(sample)

    if add_percussion:
        percs = [s for s in SAMPLE_POOL if s["type"] == "drums"]
        if percs:
            chosen.append(random.choice(percs))
    log("samples", "selection_done", {"count": len(chosen), "rejected": rejected, "percussion_added": add_percussion})
    result = {"samples": chosen}
    log("func", "exit", {"module": "sample_library.py", "function": "select_samples", "returned": len(chosen)})
    return result
