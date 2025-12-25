from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional, Dict, Any


# Store links outside step outputs to avoid changing their structure.
_LINKS_FILE = Path(__file__).resolve().parents[1] / "projects" / "output" / "step_links.json"
_LINKS_FILE.parent.mkdir(parents=True, exist_ok=True)


def _read_all() -> Dict[str, Any]:
    try:
        if not _LINKS_FILE.exists():
            return {}
        data = json.loads(_LINKS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_all(data: Dict[str, Any]) -> None:
    tmp = _LINKS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    tmp.replace(_LINKS_FILE)


def link_param_to_render(render_run_id: str, param_run_id: str) -> None:
    rid = (render_run_id or "").strip()
    pid = (param_run_id or "").strip()
    if not rid or not pid:
        return
    data = _read_all()
    rec = data.get(rid)
    if not isinstance(rec, dict):
        rec = {}
    rec["param_run_id"] = pid
    rec["updated_at"] = time.time()
    data[rid] = rec
    _write_all(data)


def get_param_for_render(render_run_id: str) -> Optional[str]:
    rid = (render_run_id or "").strip()
    if not rid:
        return None
    data = _read_all()
    rec = data.get(rid)
    if not isinstance(rec, dict):
        return None
    val = rec.get("param_run_id")
    return str(val) if isinstance(val, str) and val.strip() else None
