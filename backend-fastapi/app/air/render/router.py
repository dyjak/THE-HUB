from __future__ import annotations
from fastapi import APIRouter, HTTPException, Depends
from pathlib import Path
import json

# ten moduł wystawia endpointy fastapi dla kroku render.
#
# w skrócie:
# - `/render-audio` uruchamia właściwy render (mix + stem-y) i zapisuje stan na dysku
# - `/run/{run_id}` pozwala odtworzyć ostatni zapisany stan renderu dla danego run_id
# - `/recommend-samples` daje podpowiedzi doboru sampli na podstawie midi (bez renderowania)

from .schemas import (
    RenderRequest,
    RenderResponse,
    RecommendSamplesResponse,
    RecommendedSample,
)
from .engine import render_audio, OUTPUT_ROOT, recommend_sample_for_instrument
from app.database import get_db
from sqlalchemy.orm import Session
from app.auth.models import Proj


router = APIRouter(
    prefix="/air/render",
    tags=["air:render"],
    # uwaga: autoryzacja jest egzekwowana po stronie frontendu (/air/*),
    # a endpointy backendu w tym module są publiczne (na ten moment)
)


@router.post("/render-audio", response_model=RenderResponse)
def render_endpoint(
    req: RenderRequest,
    db: Session = Depends(get_db),
) -> RenderResponse:
    """renderuje mix oraz stem-y per instrument dla danego planu midi.

    endpoint jest celowo samowystarczalny: używa tylko docelowego silnika renderu,
    bez importowania eksperymentalnych modułów testowych.
    """

    try:
        resp = render_audio(req)
        # po udanym renderze próbujemy zapisać prosty rekord projektu powiązany z run_id
        try:
            proj = Proj(user_id=req.user_id, render=req.run_id)
            db.add(proj)
            db.commit()
        except Exception:
            # nie blokujemy odpowiedzi renderu błędem db
            db.rollback()
        # zapisujemy ostatni stan renderu dla danego run_id, aby frontend mógł go później odtworzyć
        try:
            run_dir = OUTPUT_ROOT / req.run_id
            run_dir.mkdir(parents=True, exist_ok=True)
            state_path = run_dir / "render_state.json"
            payload = {
                "request": req.dict(),
                "response": resp.dict(),
            }
            state_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        except Exception:
            # render ma priorytet: jeśli zapis stanu się nie powiedzie, nie blokujemy odpowiedzi
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


@router.post("/recommend-samples", response_model=RecommendSamplesResponse)
def recommend_samples_endpoint(req: RenderRequest) -> RecommendSamplesResponse:
    """zwraca rekomendowane sample z inventory na podstawie midi.

    endpoint służy tylko do podpowiedzi:
    - nie renderuje audio
    - niczego sam nie zapisuje

    frontend może użyć mapy instrument -> sample_id do aktualizacji planu
    (np. w meta.selected_samples).
    """

    from ..inventory.local_library import discover_samples  # lokalny import, jak w engine.py

    try:
        lib = discover_samples(deep=False)
    except Exception as e:  # noqa: PERF203
        raise HTTPException(status_code=500, detail={"error": "inventory_failed", "message": str(e)})

    # preferujemy dokładniejsze warstwy per-instrument, jeśli są obecne
    global_layers = req.midi.get("layers") or {}
    if not isinstance(global_layers, dict):
        global_layers = {}

    result: dict[str, RecommendedSample] = {}

    for track in req.tracks:
        instrument = track.instrument

        # wybór odpowiedniej warstwy midi dla danego instrumentu.
        # per-instrument midi może używać `pattern` (zwłaszcza dla perkusji)
        if req.midi_per_instrument and instrument in (req.midi_per_instrument or {}):
            inst_midi = req.midi_per_instrument[instrument] or {}
            midi_layer = inst_midi.get("pattern")
            if not isinstance(midi_layer, list) or midi_layer is None:
                midi_layer = (inst_midi.get("layers") or {}).get(instrument, [])
        else:
            midi_layer = global_layers.get(instrument, [])

        sample = recommend_sample_for_instrument(
            instrument=instrument,
            lib=lib,
            midi_layers={instrument: midi_layer},
        )

        if not sample:
            continue

        result[instrument] = RecommendedSample(
            instrument=instrument,
            sample_id=str(sample.id),
            path=str(sample.file) if getattr(sample, "file", None) else None,
            root_midi=getattr(sample, "root_midi", None),
            gain_db_normalize=getattr(sample, "gain_db_normalize", None),
        )

    return RecommendSamplesResponse(
        project_name=req.project_name,
        run_id=req.run_id,
        recommended_samples=result,
    )
