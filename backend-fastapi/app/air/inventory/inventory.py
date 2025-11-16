from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List, Tuple
import json, time


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

    def classify(rel_parts: List[str]) -> Tuple[str, str | None, str | None]:
        """Return (instrument, family, subtype) from relative path parts.
        - family: top-level pack name (first dir under root)
        - subtype: second-level detail like Kicks/Snares/Leads/etc.
        """
        parts_lower = [p.lower() for p in rel_parts]
        family = rel_parts[0] if rel_parts else None
        subtype = None
        # Prefer immediate category directories as subtype when present
        for p in reversed(parts_lower):  # check from nearest directory outward
            if p in {"kicks", "kick", "snares", "snare", "hats", "claps", "808s", "808"}:
                subtype = p
                break
            if p in {"bells", "pads", "plucks", "leads", "reese", "guitar", "bass", "flute", "sax", "synth"}:
                subtype = p
                break

        # Keyword-based instrument mapping (priority order)
        joined = "/".join(parts_lower)
        keymap: List[Tuple[str, str]] = [
            ("bass guitar", "Bass Guitar"),
            ("bass synth", "Bass Synth"),
            ("guitar", "Guitar"),
            ("flute", "Flute"),
            ("sax", "Sax"),
            ("bells", "Bells"),
            ("pads", "Pads"),
            ("plucks", "Plucks"),
            ("reese", "Reese"),
            ("lead", "Leads"),
            ("synth", "Synth"),
            ("808", "808"),
            ("kicks", "Kick"), ("kick", "Kick"),
            ("snares", "Snare"), ("snare", "Snare"),
            ("hats", "Hats"), ("claps", "Claps"),
            ("drum", "Drums"),
            ("bass", "Bass"),
        ]
        for needle, out in keymap:
            if needle in joined:
                return out, family, subtype
        # Fallback: use subtype if available, else generic "Instruments"
        return (subtype.capitalize() if subtype else "Instruments"), family, subtype

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
            try:
                rel = f.relative_to(root)
            except Exception:
                # If file is outside the expected root, skip
                continue
            rel_parts = list(rel.parts[:-1])  # directory parts only
            instrument, family, subtype = classify(rel_parts)
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
                "pitch": None,
                "category": None,
                "family": family,
                "subtype": subtype,
                "is_loop": False,
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
