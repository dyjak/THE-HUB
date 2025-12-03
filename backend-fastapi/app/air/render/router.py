from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pathlib import Path
import json

from .schemas import RenderRequest, RenderResponse
from .engine import render_audio, OUTPUT_ROOT


router = APIRouter(prefix="/air/render", tags=["air:render"])


@router.post("/render-audio", response_model=RenderResponse)
def render_endpoint(req: RenderRequest) -> RenderResponse:
    """Render mix + per-instrument stems for a given MIDI plan.

    This endpoint is intentionally self-contained and does not import
    anything from the experimental test modules.
    """

    try:
        resp = render_audio(req)
        # Zapisz ostatni stan renderu dla danego run_id, aby frontend mógł go później odtworzyć.
        try:
            run_dir = OUTPUT_ROOT / req.run_id
            run_dir.mkdir(parents=True, exist_ok=True)
            state_path = run_dir / "render_state.json"
            payload = {
                "request": req.dict(),
                "response": resp.dict(),
            }
            state_path.write_text(json.dumps(payload), encoding="utf-8")
        except Exception:
            # Render ma priorytet – jeśli zapis stanu się nie powiedzie, nie blokujemy odpowiedzi.
            pass
        return resp
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": "render_failed", "message": str(e)})


@router.get("/run/{run_id}", response_model=RenderResponse)
def get_render_run(run_id: str) -> RenderResponse:
    """Zwraca ostatni zapisany stan renderu dla danego run_id.

    Umożliwia frontowi ponowne załadowanie ustawień renderu i ścieżek audio
    po powrocie do kroku render.
    """

    run_dir = OUTPUT_ROOT / run_id
    state_path = run_dir / "render_state.json"
    if not state_path.exists():
        raise HTTPException(status_code=404, detail={"error": "render_not_found", "message": "render_state.json not found for run_id"})

    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
        resp = payload.get("response") or {}
    except Exception as e:  # noqa: PERF203
        raise HTTPException(status_code=500, detail={"error": "render_read_failed", "message": str(e)})

    try:
        return RenderResponse(**resp)
    except Exception as e:  # noqa: PERF203
        raise HTTPException(status_code=500, detail={"error": "render_state_invalid", "message": str(e)})
