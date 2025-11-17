from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List, Tuple
import json, time, re


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

        # Priority rules (most specific first)
        # 1) FX with named subtypes
        fx_subs = {
            "texture": "Texture",
            "downfilter": "Downfilter",
            "impact": "Impact",
            "swell": "Swell",
            "riser": "Riser",
            "subdrop": "Subdrop",
            "upfilter": "Upfilter",
        }
        for kw, sub in fx_subs.items():
            if kw in tokens:
                return sub, family, "FX", sub, pitch

        # 2) Drums family (excluding 808 which is its own top-level)
        drum_map = {
            "clap": "Clap",
            "hat": "Hat",
            "hihat": "Hat",
            "kick": "Kick",
            "snare": "Snare",
        }
        for kw, sub in drum_map.items():
            if kw in tokens:
                return sub, family, "Drums", sub, pitch

        # 3) 808 (treat separately from Drums)
        if "808" in tokens:
            return "808", family, None, None, pitch

        # 4) Specific compound instruments
        if "bass" in tokens and "guitar" in tokens:
            return "Bass Guitar", family, None, None, pitch
        if "bass" in tokens and "synth" in tokens:
            return "Bass Synth", family, None, None, pitch

        # 5) Single instruments (singular naming)
        single_map = [
            ("bell", "Bell"),
            ("flute", "Flute"),
            ("guitar", "Guitar"),
            ("pad", "Pad"),
            ("pluck", "Pluck"),
            ("synth", "Synth"),
            ("lead", "Lead"),
            ("reese", "Reese"),
            ("brass", "Brass"),
            ("piano", "Piano"),
            ("violin", "Violin"),
            ("sax", "Sax"),
            ("bass", "Bass"),
        ]
        for kw, inst in single_map:
            if kw in tokens:
                return inst, family, None, None, pitch

        # 6) Fallbacks based on directory hints
        # If a second-level directory suggests category, keep as that instrument in singular
        for p in reversed(rel_parts):
            pl = p.lower()
            hints = {
                "bells": "Bell", "bell": "Bell",
                "pads": "Pad", "pad": "Pad",
                "plucks": "Pluck", "pluck": "Pluck",
                "leads": "Lead", "lead": "Lead",
                "guitar": "Guitar", "flute": "Flute", "sax": "Sax",
                "reese": "Reese", "synth": "Synth", "bass": "Bass",
                "kicks": "Drums", "kick": "Drums",
                "snares": "Drums", "snare": "Drums",
                "hats": "Drums", "hat": "Drums",
                "claps": "Drums", "clap": "Drums",
                "808s": "808", "808": "808",
                "piano": "Piano", "violin": "Violin", "brass": "Brass",
            }
            if pl in hints:
                inst = hints[pl]
                cat = None
                sub = None
                if inst == "Drums":
                    # map specific to subtypes if possible
                    if "kick" in pl:
                        sub = "Kick"
                    elif "snare" in pl:
                        sub = "Snare"
                    elif "hat" in pl:
                        sub = "Hat"
                    elif "clap" in pl:
                        sub = "Clap"
                    if sub:
                        return sub, family, "Drums", sub, pitch
                    return inst, family, "Drums", None, pitch
                return inst, family, cat, sub, pitch

        # 7) Default to Synth as neutral melodic if nothing matched
        return "Synth", family, None, None, pitch

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
            rel_parts = list(rel.parts[:-1])  # directory parts only
            instrument, family, category, subtype, pitch = classify(rel_parts, f.name)
            size = 0
            try:
                size = f.stat().st_size
            except Exception:
                pass
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
            }
            if deep:
                # Placeholder: fields remain None unless an analyzer is integrated
                row.update({"sample_rate": None, "length_sec": None})
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
            json.dump(payload, f, indent=2)
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
