from __future__ import annotations

"""trwałe linkowanie runów między krokami.

`render_run_id` jest stabilnym identyfikatorem "projektu" w ui.
często chcemy wiedzieć, jaki `param_run_id` doprowadził do danego renderu.

ponieważ nie chcemy zmieniać struktury katalogów output poszczególnych kroków,
trzymamy to mapowanie w osobnym pliku `step_links.json`.
"""

import json
import time
from pathlib import Path
from typing import Optional, Dict, Any


# trzymamy linki poza outputami kroków, żeby nie zmieniać ich struktury.
_LINKS_FILE = Path(__file__).resolve().parents[1] / "projects" / "output" / "step_links.json"
_LINKS_FILE.parent.mkdir(parents=True, exist_ok=True)


def _read_all() -> Dict[str, Any]:
    """wczytuje cały plik mapowań (best-effort)."""
    try:
        if not _LINKS_FILE.exists():
            return {}
        data = json.loads(_LINKS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_all(data: Dict[str, Any]) -> None:
    """zapisuje mapowania atomowo przez plik tymczasowy."""
    tmp = _LINKS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    tmp.replace(_LINKS_FILE)


def link_param_to_render(render_run_id: str, param_run_id: str) -> None:
    """zapisuje powiązanie `render_run_id` -> `param_run_id` (best-effort)."""
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
    """odczytuje `param_run_id` powiązany z danym `render_run_id` (jeśli jest)."""
    rid = (render_run_id or "").strip()
    if not rid:
        return None
    data = _read_all()
    rec = data.get(rid)
    if not isinstance(rec, dict):
        return None
    val = rec.get("param_run_id")
    return str(val) if isinstance(val, str) and val.strip() else None
