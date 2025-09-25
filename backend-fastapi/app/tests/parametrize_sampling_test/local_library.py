from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional
from pathlib import Path
import random

# Root folder with user provided samples (outside repo or gitignored)
DEFAULT_LOCAL_SAMPLES_ROOT = Path(__file__).resolve().parents[4] / "local_samples"

SUPPORTED_EXTS = {".wav", ".aiff", ".aif", ".flac"}

@dataclass
class LocalSample:
    instrument: str
    file: Path
    id: str
    source: str = "local"
    origin_url: str | None = None
    key: str | None = None
    bpm: int | None = None


def discover_samples(root: Path = DEFAULT_LOCAL_SAMPLES_ROOT) -> Dict[str, List[LocalSample]]:
    """Walk the local sample directory and index by instrument.
    Heuristics:
      - Instrument inferred from parent directory names (lowercased) matching known tokens
      - If none matches -> bucket 'misc'
    """
    mapping: Dict[str, List[LocalSample]] = {}
    if not root.exists():
        return mapping

    known_tokens = {
        "piano": "piano",
        "pad": "pad",
        "string": "strings",
        "violin": "strings",
        "cello": "strings",
        "drum": "drums",
        "kick": "drums",
        "snare": "drums",
        "hat": "drums",
        "bass": "bass",
        "guitar": "guitar",
        "lead": "lead",
        "sax": "saxophone",
        "saxophone": "saxophone",
        "flute": "flute",
        "trumpet": "trumpet",
        "choir": "choir",
    }

    for file in root.rglob("*"):
        if not file.is_file():
            continue
        if file.suffix.lower() not in SUPPORTED_EXTS:
            continue
        parts = [p.lower() for p in file.parts]
        inst = None
        for token, normalized in known_tokens.items():
            if any(token in p for p in parts):
                inst = normalized
                break
        if inst is None:
            inst = "misc"
        sample_id = file.stem
        mapping.setdefault(inst, []).append(LocalSample(instrument=inst, file=file, id=sample_id))
    return mapping


def select_local_sample(instrument: str, index: int, library: Dict[str, List[LocalSample]]) -> Optional[LocalSample]:
    lst = library.get(instrument)
    if not lst:
        return None
    return lst[index % len(lst)]


def list_available_instruments(library: Dict[str, List[LocalSample]]) -> List[str]:
    return sorted(library.keys())
