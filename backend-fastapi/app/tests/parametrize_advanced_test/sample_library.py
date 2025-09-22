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
    # Deprecations
    if any(k in params for k in ("layers", "prefer_organic", "add_percussion")):
        log("samples", "params_deprecated", {"ignored": {k: params.get(k) for k in ("layers", "prefer_organic", "add_percussion") if k in params}})

    instruments: List[str] = midi_data.get("meta", {}).get("instruments", []) or []
    log("samples", "selection_start", {"instruments": instruments, "total_pool": len(SAMPLE_POOL)})

    chosen: List[Dict[str, Any]] = []
    for inst in instruments:
        candidates = [s for s in SAMPLE_POOL if s["type"] == inst]
        if not candidates:
            # fallback: dowolny organic jeśli dostępny, inaczej dowolny
            organic = [s for s in SAMPLE_POOL if s["organic"]]
            pick_from = organic or SAMPLE_POOL
        else:
            pick_from = candidates
        sample = random.choice(pick_from)
        chosen.append({"instrument": inst, **sample})
        log("samples", "instrument_selected", {"instrument": inst, "sample": sample["id"]})

    log("samples", "selection_done", {"count": len(chosen)})
    result = {"samples": chosen}
    log("func", "exit", {"module": "sample_library.py", "function": "select_samples", "returned": len(chosen)})
    return result
