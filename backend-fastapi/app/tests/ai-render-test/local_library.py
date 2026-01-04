from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import random
import re

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
    if any(p == "fx" for p in parts) or any(p.startswith("fx") for p in parts):
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

def _normalize_fx_subtype_from_text(text: str) -> Optional[str]:
    """Map filename text to normalized FX subtype names expected by UI.
    Normalized set: impact, downfilter, swell, riser, subdrop, upfilter
    """
    t = text.lower().replace('_', ' ')
    # remove extra punctuation while keeping word boundaries
    t = re.sub(r"[\-]+", " ", t)
    # token checks in priority order to avoid accidental matches
    checks: List[Tuple[List[str], str]] = [
        (["impact", "impacts"], "impact"),
        (["downlifter", "down lift", "downlifter"], "downfilter"),
        (["uplifter", "up lift", "uplift"], "upfilter"),
        (["riser", "rise"], "riser"),
        (["subdrop", "sub drop"], "subdrop"),
        (["swell", "swells"], "swell"),
    ]
    for keys, out in checks:
        for k in keys:
            if k in t:
                return out
    return None

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
        "leads": "lead",
        "choir": "choir",
        "flute": "flute",
        "trumpet": "trumpet",
        "sax": "saxophone",
        "saxophone": "saxophone",
        # bass family
        "bass guitar": "bass_guitar",
        "bass_guitar": "bass_guitar",
        "bass synth": "bass_synth",
        "bass_synth": "bass_synth",
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
        fx_sub = None
        # Special case: anything under an 'fx' folder indexes as instrument 'fx' with subtype
        # Prefer next folder name after 'fx' as subtype; if missing, infer from filename tokens.
        if any(p == 'fx' for p in parts):
            inst = 'fx'
            # choose subtype as the path component immediately after the first 'fx' directory if present
            try:
                # Find index of 'fx' in the directory parts (exclude filename at the end)
                dir_parts = [p.lower() for p in file.parent.parts]
                if 'fx' in dir_parts:
                    i = dir_parts.index('fx')
                    if i + 1 < len(dir_parts):
                        # normalize known synonyms if folder uses different naming
                        folder_sub = dir_parts[i+1]
                        fx_sub = _normalize_fx_subtype_from_text(folder_sub) or folder_sub
                    else:
                        fx_sub = None
                else:
                    fx_sub = None
            except Exception:
                fx_sub = None
        else:
            # Prefer longer tokens first (e.g., 'bass guitar' before 'bass')
            for token in sorted(known_tokens.keys(), key=lambda x: -len(x)):
                normalized = known_tokens[token]
                found = False
                for p in parts:
                    if token in p:
                        inst = normalized
                        found = True
                        break
                if found:
                    break
        if inst is None:
            inst = "misc"
        sample_id = file.stem
        pitch = _extract_pitch(sample_id)
        # Category & subtype/family adjustments
        category = _infer_category(parts) or ("fx" if inst in {"uplifter","downlifter","riser","impact","subdrop","fx"} else None)
        family = _infer_family(inst)
        subtype = inst
        if inst == 'fx':
            # override category and subtype for FX tree
            category = 'fx'
            # if fx_sub exists (from above), prefer it as subtype; otherwise infer from filename
            try:
                subtype = (fx_sub or _normalize_fx_subtype_from_text(file.stem) or 'fx')
            except NameError:
                subtype = (_normalize_fx_subtype_from_text(file.stem) or 'fx')
        is_loop = category == "loop"
        sample = LocalSample(instrument=inst, file=file, id=sample_id, pitch=pitch, category=category,
                             family=family, subtype=subtype, is_loop=is_loop)
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


def find_sample_by_id(library: Dict[str, List[LocalSample]], instrument: str, sample_id: str) -> Optional[LocalSample]:
    """Find a LocalSample for a given instrument by its id (filename stem)."""
    lst = library.get(instrument) or []
    for s in lst:
        if s.id == sample_id:
            return s
    return None
