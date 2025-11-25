from __future__ import annotations
from fastapi import APIRouter, HTTPException

from .schemas import RenderRequest, RenderResponse
from .engine import render_audio


router = APIRouter(prefix="/air/render", tags=["air:render"])


@router.post("/render-audio", response_model=RenderResponse)
def render_endpoint(req: RenderRequest) -> RenderResponse:
    """Render mix + per-instrument stems for a given MIDI plan.

    This endpoint is intentionally self-contained and does not import
    anything from the experimental test modules.
    """

    try:
        return render_audio(req)
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": "render_failed", "message": str(e)})
