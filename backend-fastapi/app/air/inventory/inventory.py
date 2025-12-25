from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List, Tuple
import json, time, re

from .analyze_pitch_fft import estimate_root_pitch


INVENTORY_FILE = Path(__file__).parent / "inventory.json"
INVENTORY_SCHEMA_VERSION = "air-inventory-1"

# Default root fallback if inventory.json doesn't define 'root'
# inventory.py path: backend-fastapi/app/air/inventory/inventory.py
# parents[4] points to the repository root (THE-HUB)
DEFAULT_LOCAL_SAMPLES_ROOT = Path(__file__).resolve().parents[4] / "local_samples"


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(DEFAULT_LOCAL_SAMPLES_ROOT))
    except Exception:
        return path.name


def build_inventory(deep: bool = False) -> Dict[str, Any]:
    """Scan the local_samples tree and (re)generate inventory.json.

    - Groups samples by a simple, robust keyword-based instrument classifier
    - Stores absolute + relative paths for reliable URL building later
    - Optionally (deep=True) computes basic audio stats for loudness normalisation
    - Skips unreadable/invalid audio files so broken samples never enter inventory
    - Keeps schema stable so runtime readers don't need to change
    """
    root = DEFAULT_LOCAL_SAMPLES_ROOT
    audio_exts = {".wav", ".mp3", ".aif", ".aiff", ".flac", ".ogg", ".m4a", ".wvp"}

    def _tokenize_path(parts: List[str], filename: str) -> set[str]:
        """Tokenize directory parts and filename into lowercase identifier-like tokens,
        adding simple singular forms for plural tokens (trailing 's')."""
        raw = "/".join(parts + [filename])
        toks = re.split(r"[^A-Za-z0-9#]+", raw.lower())
        out: set[str] = set()
        for t in toks:
            if not t:
                continue
            out.add(t)
            if len(t) > 3 and t.endswith("s"):
                out.add(t[:-1])
        # normalize common variants
        if "hi" in out and "hat" in out:
            out.add("hihat")
        if "hi-hat" in raw.lower():
            out.add("hihat")
        if "808s" in raw.lower():
            out.add("808")
        return out

    def _detect_pitch(name: str) -> str | None:
        """Extract pitch like A, A#3, Bb2, F from filename if present.
        Returns the last match to prefer the more specific suffix tokens."""
        # Match tokens with word-ish boundaries to reduce false positives
        # Examples: "C", "C#", "Db", "F3", "A#4"
        pat = re.compile(r"(?<![A-Za-z])([A-G])([#b]?)([0-8]?)(?![A-Za-z])")
        matches = list(pat.finditer(name))
        if not matches:
            return None
        m = matches[-1]
        note = m.group(1).upper()
        acc = m.group(2)
        octv = m.group(3)
        return note + acc + (octv or "")

    def classify(rel_parts: List[str], file_name: str) -> Tuple[str, str | None, str | None, str | None, str | None]:
        """Return (instrument, family, category, subtype, pitch) from relative path parts and filename.
        - family: top-level pack name (first dir under root)
        - category: grouping like Drums or FX for certain instruments; else None
        - subtype: optional detail label (often equals instrument for grouped types)
        - pitch: extracted from filename when found
        """
        tokens = _tokenize_path(rel_parts, file_name)
        family = rel_parts[0] if rel_parts else None
        pitch = _detect_pitch(file_name)

        name_upper = file_name.upper()

        # 1) Explicit name-based rules from spec
        # Acoustic Guitar: filename contains "ACOUSTICG"
        if "ACOUSTICG" in name_upper:
            return "Acoustic Guitar", family, None, None, pitch

        # Electric Guitar: filename contains "DARK STAL METAL"
        if "DARK STAR METAL" in name_upper:
            return "Electric Guitar", family, None, None, pitch

        # Bass Guitar: filename contains "DEEPER PURPLE"
        if "DEEPER PURPLE" in name_upper:
            return "Bass Guitar", family, None, None, pitch

        # Trombone: filename contains "TRO MLON"
        if "TRO MLON" in name_upper:
            return "Trombone", family, None, None, pitch

        # Piano specials: "CHANGPIANOHARD" or prefix "Gz_"
        if "CHANGPIANOHARD" in name_upper or name_upper.startswith("GZ_"):
            return "Piano", family, None, None, pitch

        # 2) Folder-based high-level families
        # Top-level folders are already reflected in `family` from rel_parts[0]
        if family:
            fam_low = family.lower()
            if fam_low == "choirs":
                return "Choirs", family, None, None, pitch
            if fam_low == "fx":
                # FX without subcategories
                return "FX", family, "FX", None, pitch
            if fam_low == "pads":
                return "Pads", family, None, None, pitch
            if fam_low == "strings":
                return "Strings", family, None, None, pitch
            if fam_low == "sax":
                return "Sax", family, None, None, pitch
            if fam_low == "trombone":
                return "Trombone", family, None, None, pitch
            if fam_low == "piano":
                return "Piano", family, None, None, pitch

        # 3) Drums with detailed subtypes
        # We treat all of them under category "Drums" with subtypes
        drum_subs = {
            "clap": "Clap",
            "hat": "Hat",
            "hihat": "Hat",
            "kick": "Kick",
            "snare": "Snare",
            "crash": "Crash",
            "ride": "Ride",
            "splash": "Splash",
            "tom": "Tom",
            "rim": "Rim",
            "shake": "Shake",
            "shaker": "Shake",
        }
        for kw, sub in drum_subs.items():
            if kw in tokens:
                return sub, family or "Drums", "Drums", sub, pitch

        # 4) Remaining broader instrument categories
        # Uwaga: nie dodajemy ogólnego fallbacku "guitar" tutaj, żeby nie mylić Electric/Acoustic.
        single_map = [
            ("choir", "Choirs"),
            ("string", "Strings"),
            ("sax", "Sax"),
            ("trombone", "Trombone"),
            ("pad", "Pads"),
            ("piano", "Piano"),
            ("bass", "Bass"),
        ]
        for kw, inst in single_map:
            if kw in tokens:
                return inst, family, None, None, pitch

        # 5) Default to FX or Synth depending on folder
        if family and family.lower() == "fx":
            return "FX", family, "FX", None, pitch

        # Neutral melodic default
        return "Pads", family, None, None, pitch

    instruments: Dict[str, Any] = {}
    all_samples: list[dict[str, Any]] = []
    total_files = 0
    total_bytes = 0

    try:
        for f in root.rglob("*"):
            if not f.is_file():
                continue
            if f.suffix.lower() not in audio_exts:
                continue
            # Skip specific FX we don't want in the inventory
            name_lower = f.name.lower()
            if "downlifter" in name_lower or "uplifter" in name_lower:
                continue
            try:
                rel = f.relative_to(root)
            except Exception:
                # If file is outside the expected root, skip
                continue

            # Lightweight validity check: try opening audio file once.
            # This ensures corrupt/unreadable files never reach the inventory
            # and therefore nie pojawią się w panelu ani w playbacku.
            try:
                if f.suffix.lower() == ".wav":
                    import wave as _wav  # type: ignore
                    with _wav.open(str(f), "rb") as _wf:  # type: ignore
                        _ = _wf.getnframes()
                else:
                    # For now other formats are trusted; extend here if needed.
                    pass
            except Exception:
                # Broken / unreadable file -> completely skip
                continue

            rel_parts = list(rel.parts[:-1])  # directory parts only
            instrument, family, category, subtype, pitch = classify(rel_parts, f.name)
            size = 0
            try:
                size = f.stat().st_size
            except Exception:
                pass

            # Optional deep analysis for loudness/length if requested.
            sample_rate: int | None = None
            length_sec: float | None = None
            loudness_rms: float | None = None
            gain_db_normalize: float | None = None
            root_midi: float | None = None
            if deep:
                try:
                    import wave as _wav  # type: ignore
                    import contextlib as _ctx  # type: ignore
                    import math as _math  # type: ignore
                    with _ctx.closing(_wav.open(str(f), "rb")) as wf:
                        sr = wf.getframerate()
                        n_channels = wf.getnchannels()
                        n_frames = wf.getnframes()
                        # limit frames for RMS to keep it quick on huge files
                        max_frames = min(n_frames, sr * 60)
                        frames = wf.readframes(max_frames)
                        import struct as _struct  # type: ignore

                        if wf.getsampwidth() == 2 and n_channels > 0:
                            total_samples = max_frames * n_channels
                            fmt = "<" + "h" * total_samples
                            try:
                                ints = _struct.unpack(fmt, frames)
                                # downmix to mono by taking first channel
                                mono = ints[0::n_channels]
                                if mono:
                                    # normalise to [-1, 1]
                                    vals = [x / 32768.0 for x in mono]
                                    n = float(len(vals))
                                    if n > 0:
                                        rms = _math.sqrt(sum(v * v for v in vals) / n)
                                        loudness_rms = float(rms)
                                        # baseline target ~0.2 (arbitrary but sensible for headroom)
                                        target = 0.2
                                        if rms > 0:
                                            gain_db_normalize = float(-20.0 * _math.log10(rms / target))
                            except Exception:
                                pass
                        sample_rate = int(sr)
                        if sr > 0:
                            length_sec = float(n_frames) / float(sr)
                except Exception:
                    pass

                # Optional FFT-based pitch estimation for root note
                try:
                    est = estimate_root_pitch(f)
                    if est and "pitch_midi" in est:
                        root_midi = float(est["pitch_midi"])
                except Exception:
                    root_midi = None

            row = {
                "instrument": instrument,
                "id": rel.as_posix(),  # stable, human-inspectable id
                "file_rel": rel.as_posix(),
                "file_abs": str(f.resolve()),
                "bytes": size,
                "source": "local",
                "pitch": pitch,
                "category": category,
                "family": family,
                "subtype": subtype,
                "root_midi": root_midi,
                "sample_rate": sample_rate,
                "length_sec": length_sec,
                "loudness_rms": loudness_rms,
                "gain_db_normalize": gain_db_normalize,
            }
            all_samples.append(row)
            total_files += 1
            total_bytes += size
            inst_meta = instruments.setdefault(instrument, {"count": 0, "examples": []})
            inst_meta["count"] += 1
            if len(inst_meta["examples"]) < 5:
                inst_meta["examples"].append(f.name)
    except FileNotFoundError:
        # Empty inventory when folder is missing
        pass
    # Determine root: prefer existing inventory root, else fallback
    try:
        existing = load_inventory() or {}
        root_str = existing.get("root") or str(DEFAULT_LOCAL_SAMPLES_ROOT)
    except Exception:
        root_str = str(DEFAULT_LOCAL_SAMPLES_ROOT)

    payload = {
        "schema_version": INVENTORY_SCHEMA_VERSION,
        "generated_at": time.time(),
        "root": root_str,
        "instrument_count": len(instruments),
        "total_files": total_files,
        "total_bytes": total_bytes,
        "instruments": instruments,
        "samples": all_samples,
        "deep": deep,
    }
    try:
        with INVENTORY_FILE.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
    except Exception:
        pass
    return payload


def load_inventory() -> Dict[str, Any] | None:
    if not INVENTORY_FILE.exists():
        return None
    try:
        return json.loads(INVENTORY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None
