from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
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
    key: str | None = None          # musical key if known
    bpm: int | None = None          # bpm if encoded in name
    subtype: str | None = None      # granular subtype (e.g. kick, snare, uplifter)
    family: str | None = None       # higher level grouping (drum, fx, melodic, bass)
    category: str | None = None     # semantic usage: oneshot, loop, fx, instrument
    pitch: str | None = None        # extracted pitch token
    is_loop: bool = False
    sample_rate: int | None = None  # only filled in deep mode
    length_sec: float | None = None # only filled in deep mode


PITCH_TOKENS = ["c","c#","db","d","d#","eb","e","f","f#","gb","g","g#","ab","a","a#","bb","b"]

def _extract_pitch(name: str) -> Optional[str]:
    low = name.lower().replace("-", " ")
    parts = [p.strip() for p in low.replace("_"," ").split() if p.strip()]
    for p in parts:
        if p in PITCH_TOKENS:
            # normalise enharmonic flats to sharps for simplicity
            mapping = {"db":"c#","eb":"d#","gb":"f#","ab":"g#","bb":"a#"}
            return mapping.get(p, p).upper()
    return None

def _infer_category(parts: List[str]) -> Optional[str]:
    if any("loop" in p for p in parts):
        return "loop"
    if any("fx" in p for p in parts):
        return "fx"
    if any("oneshot" in p for p in parts):
        return "oneshot"
    return None

def _infer_family(inst: str) -> str:
    if inst in {"kick","snare","hihat","clap","rim","tom","808","perc","drum","drumkit"}:
        return "drum"
    if inst in {"uplifter","downlifter","riser","impact","subdrop","fx"}:
        return "fx"
    if inst in {"bass","reese","bass_guitar","bass_synth"}:
        return "bass"
    return "melodic"

def discover_samples(root: Path = DEFAULT_LOCAL_SAMPLES_ROOT, deep: bool = False) -> Dict[str, List[LocalSample]]:
    """Walk the local sample directory and index by instrument.
    Heuristics:
      - Instrument inferred from parent directory names (lowercased) matching known tokens
      - If none matches -> bucket 'misc'
    """
    mapping: Dict[str, List[LocalSample]] = {}
    if not root.exists():
        return mapping

    # Map filename/path tokens to canonical instrument names. Drum sub-types remain distinct
    # so that e.g. kick + snare + hihat can co‑exist as separate logical instruments.
    known_tokens = {
        # melodic / harmonic
        "piano": "piano",
        "pad": "pad",
        "string": "strings",
        "strings": "strings",
        "violin": "strings",
        "cello": "strings",
        "lead": "lead",
        "choir": "choir",
        "flute": "flute",
        "trumpet": "trumpet",
        "sax": "saxophone",
        "saxophone": "saxophone",
        # bass family
        "bass": "bass",
        "reese": "reese",
        # granular percussion singular/plural
        "kick": "kick", "kicks": "kick",
        "snare": "snare", "snares": "snare",
        "clap": "clap", "claps": "clap",
        "hat": "hihat", "hihat": "hihat", "hats": "hihat",
        "rim": "rim", "toms": "tom", "tom": "tom",
        "808": "808", "808s": "808",
        "perc": "perc", "percussion": "perc",
        "drumkit": "drumkit", "drum": "drumkit", "drums": "drumkit",
        # fx & transitions
        "uplifter": "uplifter", "uplift": "uplifter",
        "downlifter": "downlifter", "downlift": "downlifter",
        "riser": "riser", "rise": "riser",
        "impact": "impact", "impacts": "impact",
        "subdrop": "subdrop", "subdrops": "subdrop",
        "fx": "fx",
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
        pitch = _extract_pitch(sample_id)
        category = _infer_category(parts) or ("fx" if inst in {"uplifter","downlifter","riser","impact","subdrop","fx"} else None)
        family = _infer_family(inst)
        is_loop = category == "loop"
        sample = LocalSample(instrument=inst, file=file, id=sample_id, pitch=pitch, category=category,
                             family=family, subtype=inst, is_loop=is_loop)
        if deep:
            try:
                import wave
                with wave.open(str(file), 'rb') as wf:
                    sr = wf.getframerate(); frames = wf.getnframes()
                    sample.sample_rate = sr
                    sample.length_sec = frames / float(sr) if sr else None
            except Exception:
                pass
        mapping.setdefault(inst, []).append(sample)
    return mapping


def select_local_sample(instrument: str, index: int, library: Dict[str, List[LocalSample]]) -> Optional[LocalSample]:
    lst = library.get(instrument)
    if not lst:
        return None
    return lst[index % len(lst)]


def list_available_instruments(library: Dict[str, List[LocalSample]]) -> List[str]:
    return sorted(library.keys())
