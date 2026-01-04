from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional
from pathlib import Path
import json

# ten moduł udostępnia "bibliotekę lokalnych sampli" na podstawie inventory.json.
#
# ważna decyzja projektowa:
# - w runtime nie skanujemy filesystemu i nie klasyfikujemy plików na nowo
# - zamiast tego opieramy się wyłącznie na tym, co jest już zapisane w inventory.json
# - dzięki temu zachowanie jest deterministyczne i szybkie, a cięższy skan jest tylko w build_inventory
#
# wczytujemy json bezpośrednio tutaj, żeby uniknąć cyklicznych importów z inventory.py
INVENTORY_FILE = Path(__file__).parent / "inventory.json"

def _load_inventory() -> dict | None:
    # bezpieczne wczytanie inventory.json (zwraca None, jeśli pliku nie ma lub jest uszkodzony)
    try:
        if not INVENTORY_FILE.exists():
            return None
        return json.loads(INVENTORY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


@dataclass
class LocalSample:
    # rekord opisujący pojedynczy sample dostępny lokalnie.
    # pola pochodzą bezpośrednio z inventory.json.
    instrument: str
    file: Path
    id: str
    source: str = "local"
    pitch: str | None = None
    root_midi: float | None = None
    category: str | None = None
    family: str | None = None
    subtype: str | None = None
    is_loop: bool = False
    sample_rate: int | None = None
    length_sec: float | None = None
    loudness_rms: float | None = None
    gain_db_normalize: float | None = None


def _abs_path(root: Path, row: dict) -> Path:
    # preferujemy ścieżkę absolutną z inventory; jeśli jej nie ma, liczymy ją z file_rel + root
    f_abs = row.get("file_abs")
    if f_abs:
        return Path(f_abs)
    f_rel = row.get("file_rel")
    if f_rel:
        return (root / f_rel).resolve()
    # fallback: próbujemy z id
    return (root / str(row.get("id") or "")).resolve()


def _rows_by_instrument(inv: dict) -> Dict[str, List[dict]]:
    # grupuje wiersze `samples` z inventory według pola `instrument`
    out: Dict[str, List[dict]] = {}
    samples = inv.get("samples") or []
    for row in samples:
        inst = row.get("instrument")
        if not inst:
            continue
        out.setdefault(inst, []).append(row)
    return out


def discover_samples(deep: bool = False) -> Dict[str, List[LocalSample]]:
    """buduje mapę instrument -> lista LocalSample wyłącznie na podstawie inventory.json.

    uwagi:
    - parametr `deep` jest ignorowany: zakładamy, że jeśli potrzebne były dane "deep",
      to zostały już policzone i zapisane w inventory.json na etapie build_inventory.
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
                    root_midi=r.get("root_midi"),
                    category=r.get("category"),
                    family=r.get("family"),
                    subtype=r.get("subtype"),
                    is_loop=bool(r.get("is_loop", False)),
                    sample_rate=r.get("sample_rate"),
                    length_sec=r.get("length_sec"),
                    loudness_rms=r.get("loudness_rms"),
                    gain_db_normalize=r.get("gain_db_normalize"),
                )
                lst.append(s)
            except Exception:
                continue
        mapping[inst] = lst
    return mapping


def list_available_instruments(lib: Dict[str, List[LocalSample]]) -> List[str]:
    # zwraca posortowaną listę instrumentów dostępnych w bibliotece
    return sorted(lib.keys())


def find_sample_by_id(lib: Dict[str, List[LocalSample]], instrument: str, sample_id: str) -> Optional[LocalSample]:
    # znajduje sample po id w obrębie konkretnego instrumentu
    for s in lib.get(instrument, []) or []:
        if s.id == sample_id:
            return s
    return None
