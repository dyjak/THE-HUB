from __future__ import annotations

"""endpointy projektów użytkownika.

ten moduł łączy dwa źródła danych:
- baza (`projs`): mapowanie użytkownik -> render run_id
- pliki na dysku (`render_state.json` i outputy kroków): szczegóły renderu i metadane

zwracane rekordy są wzbogacane best-effort o:
- prompt i meta z param_generation (jeśli umiemy rozwiązać param_run_id)
- informacje o wybranych samplach (nazwa/url/pitch) na podstawie inventory.json
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from urllib.parse import quote
from pathlib import Path
import re

from app.database import get_db
from app.auth.models import Proj
from .render.engine import OUTPUT_ROOT
from .render.schemas import RenderResponse

from app.air.export.links import get_param_for_render
from app.air.inventory.access import get_inventory_cached

router = APIRouter(
    prefix="/air/user-projects",
    tags=["air:user-projects"],
)


PARAM_OUTPUT_DIR = Path(__file__).resolve().parent / "param_generation" / "output"


_PARAM_DIR_RE = re.compile(r"^\d{8}_\d{6}_(.+)$")


def _iso(dt: Any) -> Optional[str]:
    """formatuje datę na iso (best-effort)."""
    try:
        if dt is None:
            return None
        # created_at jest przechowywane jako naive utc w db
        return dt.replace(microsecond=0).isoformat() + "Z"
    except Exception:
        try:
            return str(dt)
        except Exception:
            return None


def _load_json_file(path: Path) -> Optional[Dict[str, Any]]:
    """wczytuje json jako dict (best-effort)."""
    try:
        if not path.exists() or not path.is_file():
            return None
        import json

        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _find_param_plan_doc(param_run_id: str) -> Optional[Dict[str, Any]]:
    """próbuje znaleźć `parameter_plan.json` dla danego `param_run_id`.

    folder param_generation ma zwykle prefix z timestampem, więc szukamy po sufiksie.
    """
    rid = (param_run_id or "").strip()
    if not rid:
        return None
    try:
        if not PARAM_OUTPUT_DIR.exists() or not PARAM_OUTPUT_DIR.is_dir():
            return None
        matches: List[Path] = []
        for p in PARAM_OUTPUT_DIR.iterdir():
            if not p.is_dir():
                continue
            if p.name.endswith(rid) and (p / "parameter_plan.json").exists():
                matches.append(p)
        if not matches:
            return None
        # preferujemy najnowszy folder z timestampem
        matches.sort(key=lambda x: x.name, reverse=True)
        return _load_json_file(matches[0] / "parameter_plan.json")
    except Exception:
        return None


def _extract_prompt(plan_doc: Optional[Dict[str, Any]]) -> Optional[str]:
    """wyciąga prompt użytkownika z dokumentu planu (jeśli jest)."""
    if not isinstance(plan_doc, dict):
        return None
    for key in ("user_prompt", "prompt"):
        v = plan_doc.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    meta = plan_doc.get("meta")
    if isinstance(meta, dict):
        for key in ("user_prompt", "prompt"):
            v = meta.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()
    return None


def _extract_param_meta(plan_doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """wyciąga pole `meta` z dokumentu planu (jeśli jest dict-em)."""
    if not isinstance(plan_doc, dict):
        return None
    meta = plan_doc.get("meta")
    return meta if isinstance(meta, dict) else None


def _param_run_id_from_dir_name(dir_name: str) -> Optional[str]:
    """wydobywa run_id z nazwy folderu `<timestamp>_<run_id>` (best-effort)."""
    try:
        m = _PARAM_DIR_RE.match(dir_name or "")
        if not m:
            return None
        rid = (m.group(1) or "").strip()
        return rid or None
    except Exception:
        return None


def _normalize_selected_samples(selected_samples: Dict[str, str]) -> Dict[str, str]:
    """normalizuje mapę instrument -> sample_id (strip, filtr typów)."""
    out: Dict[str, str] = {}
    if not isinstance(selected_samples, dict):
        return out
    for k, v in selected_samples.items():
        if not isinstance(k, str) or not isinstance(v, str):
            continue
        kk = k.strip()
        vv = v.strip()
        if kk and vv:
            out[kk] = vv
    return out


def _infer_param_plan_from_selected_samples(
    selected_samples: Dict[str, str],
) -> tuple[Optional[str], Optional[Dict[str, Any]]]:
    """best-effort mapowanie render -> param plan, gdy brakuje step_links.json.

    szukamy `parameter_plan.json`, którego `meta.selected_samples` dokładnie pasuje
    do `selected_samples` z requestu renderu.
    """

    target = _normalize_selected_samples(selected_samples)
    if not target:
        return None, None
    try:
        if not PARAM_OUTPUT_DIR.exists() or not PARAM_OUTPUT_DIR.is_dir():
            return None, None
    except Exception:
        return None, None

    # preferujemy najnowsze foldery jako pierwsze
    try:
        dirs = [p for p in PARAM_OUTPUT_DIR.iterdir() if p.is_dir() and (p / "parameter_plan.json").exists()]
        dirs.sort(key=lambda p: p.name, reverse=True)
    except Exception:
        return None, None

    for d in dirs:
        doc = _load_json_file(d / "parameter_plan.json")
        meta = _extract_param_meta(doc)
        if not isinstance(meta, dict):
            continue
        ss = meta.get("selected_samples")
        if not isinstance(ss, dict):
            continue
        if _normalize_selected_samples(ss) == target:
            return _param_run_id_from_dir_name(d.name), doc

    return None, None


def _resolve_selected_samples_info(selected_samples: Dict[str, str]) -> Dict[str, Dict[str, Any]]:
    """mapuje wybrane sample_id na czytelne info na podstawie inventory.json.

    `inventory.json` używa stabilnych id opartych o ścieżki względne.
    zwracamy kompaktowy obiekt per instrument, żeby ui mogło to wyświetlić.
    """

    try:
        inv = get_inventory_cached()
    except Exception:
        inv = {}

    rows = inv.get("samples") or []
    if not isinstance(rows, list) or not selected_samples:
        return {}

    by_id: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        rid = r.get("id")
        if isinstance(rid, str) and rid:
            by_id[rid] = r

    out: Dict[str, Dict[str, Any]] = {}
    for instrument, sid in (selected_samples or {}).items():
        if not isinstance(instrument, str) or not isinstance(sid, str):
            continue
        inst = instrument.strip()
        sample_id = sid.strip()
        if not inst or not sample_id:
            continue

        row = by_id.get(sample_id)
        name = None
        pitch = None
        subtype = None
        family = None
        category = None
        url = None

        if isinstance(row, dict):
            pitch = row.get("pitch")
            subtype = row.get("subtype")
            family = row.get("family")
            category = row.get("category")
            try:
                file_rel = row.get("file_rel")
                file_abs = row.get("file_abs")
                if isinstance(file_rel, str) and file_rel:
                    name = Path(file_rel).name
                    url = "/api/local-samples/" + quote(Path(file_rel).as_posix(), safe="/")
                elif isinstance(file_abs, str) and file_abs:
                    name = Path(file_abs).name
            except Exception:
                name = None

        if not name:
            # fallback: id wygląda jak ścieżka względna
            try:
                name = Path(sample_id).name
            except Exception:
                name = sample_id

        out[inst] = {
            "id": sample_id,
            "name": name,
            "url": url,
            "pitch": pitch,
            "subtype": subtype,
            "family": family,
            "category": category,
        }

    return out


@router.get("/by-user")
def list_projects_for_user(
    user_id: int = Query(..., description="ID aktualnego użytkownika (z frontendu)"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> List[dict]:
    """Zwraca listę ostatnich renderów powiązanych z danym użytkownikiem.

    Używa tabeli projs (Proj.user_id, Proj.render), a szczegóły renderu
    wczytuje z pliku render_state.json dla danego run_id.
    """

    projects: List[Proj] = (
        db.query(Proj)
        .filter(Proj.user_id == user_id)
        .order_by(Proj.created_at.desc())
        .limit(limit)
        .all()
    )

    results: List[dict] = []

    for proj in projects:
        run_id: Optional[str] = proj.render
        if not run_id:
            continue

        state_path = OUTPUT_ROOT / run_id / "render_state.json"
        if not state_path.exists():
            continue

        try:
            import json

            payload = json.loads(state_path.read_text(encoding="utf-8"))
            resp_data = payload.get("response") or {}
            rr = RenderResponse(**resp_data)

            req_data = payload.get("request") if isinstance(payload.get("request"), dict) else {}
            midi_meta = None
            try:
                midi_obj = req_data.get("midi") if isinstance(req_data, dict) else None
                if isinstance(midi_obj, dict):
                    mm = midi_obj.get("meta")
                    midi_meta = mm if isinstance(mm, dict) else None
            except Exception:
                midi_meta = None

            # best-effort: wzbogacamy o prompt + param meta, jeśli umiemy rozwiązać param_run_id
            param_run_id = None
            prompt = None
            param_meta = None
            try:
                param_run_id = get_param_for_render(run_id)
                plan_doc = _find_param_plan_doc(param_run_id) if param_run_id else None
                prompt = _extract_prompt(plan_doc)
                param_meta = _extract_param_meta(plan_doc)
            except Exception:
                param_run_id = None
                prompt = None
                param_meta = None

            # fallback: jeśli brakuje linków (albo rekordu), próbujemy wywnioskować plan
            # przez dopasowanie `selected_samples`.
            plan_doc = None
            if prompt is None or param_meta is None or not param_run_id:
                try:
                    ss_req = req_data.get("selected_samples") if isinstance(req_data, dict) else None
                    if isinstance(ss_req, dict):
                        inferred_run_id, inferred_doc = _infer_param_plan_from_selected_samples(ss_req)
                        if inferred_doc:
                            plan_doc = inferred_doc
                            if not param_run_id:
                                param_run_id = inferred_run_id
                            if prompt is None:
                                prompt = _extract_prompt(plan_doc)
                            if param_meta is None:
                                param_meta = _extract_param_meta(plan_doc)
                except Exception:
                    pass

            # źródło selected_samples: preferujemy param meta, a w fallbacku request renderu
            selected_samples: Dict[str, str] | None = None
            try:
                if isinstance(param_meta, dict) and isinstance(param_meta.get("selected_samples"), dict):
                    selected_samples = {
                        str(k): str(v)
                        for k, v in (param_meta.get("selected_samples") or {}).items()
                        if isinstance(k, str) and isinstance(v, str) and k.strip() and v.strip()
                    }
                else:
                    ss = req_data.get("selected_samples") if isinstance(req_data, dict) else None
                    if isinstance(ss, dict):
                        selected_samples = {
                            str(k): str(v)
                            for k, v in ss.items()
                            if isinstance(k, str) and isinstance(v, str) and k.strip() and v.strip()
                        }
            except Exception:
                selected_samples = None

            selected_samples_info = _resolve_selected_samples_info(selected_samples or {}) if selected_samples else {}

            results.append({
                "project_id": proj.id,
                "created_at": _iso(getattr(proj, "created_at", None)),
                "param_run_id": param_run_id,
                "prompt": prompt,
                "param_meta": param_meta,
                "midi_meta": midi_meta,
                "selected_samples": selected_samples,
                "selected_samples_info": selected_samples_info or None,
                **rr.dict(),
            })
        except Exception:
            # jeśli pojedynczy projekt ma uszkodzony plik, pomijamy go
            continue

    return results


@router.patch("/rename")
def rename_project(
    project_id: int = Query(..., description="ID rekordu w tabeli projs"),
    name: str = Query(..., min_length=1, max_length=200, description="Nowa nazwa projektu"),
    db: Session = Depends(get_db),
):
    """Zmienia nazwę projektu zapisując ją w render_state.json.

    Z poziomu bazy mamy tylko powiązanie user_id <-> run_id, więc nazwa
    przechowywana jest w JSON-ie stanu renderu.
    """

    proj: Optional[Proj] = db.query(Proj).filter(Proj.id == project_id).first()
    if not proj or not proj.render:
        raise HTTPException(status_code=404, detail="project_not_found")

    run_id = proj.render
    state_path = OUTPUT_ROOT / run_id / "render_state.json"
    if not state_path.exists():
        raise HTTPException(status_code=404, detail="render_state_not_found")

    import json

    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        raise HTTPException(status_code=500, detail="state_read_failed")

    resp = payload.get("response") or {}
    resp["project_name"] = name
    payload["response"] = resp

    try:
        state_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    except Exception:
        raise HTTPException(status_code=500, detail="state_write_failed")

    return {"status": "ok"}


@router.delete("/delete")
def delete_project(
    project_id: int = Query(..., description="ID rekordu w tabeli projs"),
    db: Session = Depends(get_db),
):
    """Usuwa rekord projektu z tabeli projs.

    Pliki audio i render_state.json pozostają na dysku; zakładamy prosty,
    nieinwazyjny model, w którym usuwamy tylko powiązanie użytkownik-projekt.
    """

    proj: Optional[Proj] = db.query(Proj).filter(Proj.id == project_id).first()
    if not proj:
        raise HTTPException(status_code=404, detail="project_not_found")

    db.delete(proj)
    db.commit()

    return {"status": "ok"}
