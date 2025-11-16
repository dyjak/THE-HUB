from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional
from pathlib import Path
import json

# Production local_library: derive everything from inventory.json only (no token maps, no FS heurystyki)
# Load JSON directly here to avoid circular imports with inventory.py
INVENTORY_FILE = Path(__file__).parent / "inventory.json"

def _load_inventory() -> dict | None:
    try:
        if not INVENTORY_FILE.exists():
            return None
        return json.loads(INVENTORY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


@dataclass
class LocalSample:
    instrument: str
    file: Path
    id: str
    source: str = "local"
    pitch: str | None = None
    category: str | None = None
    family: str | None = None
    subtype: str | None = None
    is_loop: bool = False
    sample_rate: int | None = None
    length_sec: float | None = None


def _abs_path(root: Path, row: dict) -> Path:
    # Prefer explicit absolute path from inventory; else resolve from file_rel + root
    f_abs = row.get("file_abs")
    if f_abs:
        return Path(f_abs)
    f_rel = row.get("file_rel")
    if f_rel:
        return (root / f_rel).resolve()
    # Fallback: name only
    return (root / str(row.get("id") or "")).resolve()


def _rows_by_instrument(inv: dict) -> Dict[str, List[dict]]:
    out: Dict[str, List[dict]] = {}
    samples = inv.get("samples") or []
    for row in samples:
        inst = row.get("instrument")
        if not inst:
            continue
        out.setdefault(inst, []).append(row)
    return out


def discover_samples(deep: bool = False) -> Dict[str, List[LocalSample]]:
    """Build instrument->LocalSample map from inventory.json exclusively.
    'deep' flag is ignored; relies on fields already present in inventory.json.
    """
    inv = _load_inventory()
    mapping: Dict[str, List[LocalSample]] = {}
    if not isinstance(inv, dict):
        return mapping
    root = Path(inv.get("root") or ".").resolve()
    rows_by_inst = _rows_by_instrument(inv)
    for inst, rows in rows_by_inst.items():
        lst: List[LocalSample] = []
        for r in rows:
            try:
                s = LocalSample(
                    instrument=inst,
                    file=_abs_path(root, r),
                    id=str(r.get("id")),
                    source=str(r.get("source") or "local"),
                    pitch=r.get("pitch"),
                    category=r.get("category"),
                    family=r.get("family"),
                    subtype=r.get("subtype"),
                    is_loop=bool(r.get("is_loop", False)),
                    sample_rate=r.get("sample_rate"),
                    length_sec=r.get("length_sec"),
                )
                lst.append(s)
            except Exception:
                continue
        mapping[inst] = lst
    return mapping


def list_available_instruments(lib: Dict[str, List[LocalSample]]) -> List[str]:
    return sorted(lib.keys())


def find_sample_by_id(lib: Dict[str, List[LocalSample]], instrument: str, sample_id: str) -> Optional[LocalSample]:
    for s in lib.get(instrument, []) or []:
        if s.id == sample_id:
            return s
    return None
