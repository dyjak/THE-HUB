from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, Optional
import json

ROOT = Path(__file__).parent / "output"
ROOT.mkdir(parents=True, exist_ok=True)


def _project_path(project_id: str) -> Path:
    return ROOT / f"{project_id}.json"


def load_project(project_id: str) -> Optional[Dict[str, Any]]:
    path = _project_path(project_id)
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_project(project_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    path = _project_path(project_id)
    existing: Dict[str, Any] = {}
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as f:
                existing = json.load(f) or {}
        except Exception:
            existing = {}
    merged = {**existing, **data}
    merged["project_id"] = project_id
    with path.open("w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    return merged
