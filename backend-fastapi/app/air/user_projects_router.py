from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.models import Proj
from .render.engine import OUTPUT_ROOT
from .render.schemas import RenderResponse

router = APIRouter(
    prefix="/air/user-projects",
    tags=["air:user-projects"],
)


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
            results.append({
                "project_id": proj.id,
                **rr.dict(),
            })
        except Exception:
            # Jeśli pojedynczy projekt ma uszkodzony plik, pomijamy go
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
