from __future__ import annotations
from pathlib import Path
from typing import Dict, Any
import json, time, os
from .local_library import discover_samples, LocalSample, DEFAULT_LOCAL_SAMPLES_ROOT

INVENTORY_FILE = Path(__file__).parent / "inventory.json"
INVENTORY_SCHEMA_VERSION = "3"  # increment on breaking shape changes

def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(DEFAULT_LOCAL_SAMPLES_ROOT))
    except Exception:
        return path.name

def build_inventory(deep: bool = False) -> Dict[str, Any]:
    lib = discover_samples(deep=deep)
    instruments: Dict[str, Any] = {}
    all_samples: list[dict[str, Any]] = []
    total_files = 0
    total_bytes = 0
    for inst, samples in lib.items():
        instruments[inst] = {
            "count": len(samples),
            "examples": [s.file.name for s in samples[:5]],
        }
        for s in samples:
            size = 0
            try:
                size = s.file.stat().st_size
            except Exception:
                pass
            total_files += 1
            total_bytes += size
            all_samples.append({
                "instrument": inst,
                "id": s.id,
                "file_rel": _rel(s.file),
                "file_abs": str(s.file),
                "bytes": size,
                "source": s.source,
                "pitch": s.pitch,
                "category": s.category,
                "family": s.family,
                "subtype": s.subtype,
                "is_loop": s.is_loop,
                **({"sample_rate": s.sample_rate, "length_sec": s.length_sec} if deep else {})
            })
    payload = {
        "schema_version": INVENTORY_SCHEMA_VERSION,
        "generated_at": time.time(),
        "root": str(DEFAULT_LOCAL_SAMPLES_ROOT),
        "instrument_count": len(instruments),
        "total_files": total_files,
        "total_bytes": total_bytes,
        "instruments": instruments,         # concise view
        "samples": all_samples,             # detailed rows
        "deep": deep,
    }
    try:
        with INVENTORY_FILE.open('w', encoding='utf-8') as f:
            json.dump(payload, f, indent=2)
    except Exception:
        pass
    return payload

def load_inventory() -> Dict[str, Any] | None:
    if not INVENTORY_FILE.exists():
        return None
    try:
        return json.loads(INVENTORY_FILE.read_text(encoding='utf-8'))
    except Exception:
        return None