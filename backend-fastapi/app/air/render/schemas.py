from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional


class TrackSettings(BaseModel):
    instrument: str
    enabled: bool = True
    volume_db: float = Field(0.0, ge=-60.0, le=6.0)
    pan: float = Field(0.0, ge=-1.0, le=1.0, description="-1 = left, 0 = center, 1 = right")


class RenderRequest(BaseModel):
    """Request payload for audio rendering step.

    Currently only volume and pan are used by the renderer.
    """

    project_name: str = Field(..., min_length=1, max_length=200)
    run_id: str = Field(..., min_length=1)
    midi: Dict[str, Any]
    # Opcjonalnie pełny podział MIDI per instrument z modułu midi_generation.
    midi_per_instrument: Dict[str, Dict[str, Any]] | None = None
    tracks: List[TrackSettings]
    # instrument -> inventory sample id (row.id) or resolved file path
    selected_samples: Dict[str, str] | None = None


class RenderedStem(BaseModel):
    instrument: str
    audio_rel: str


class RenderResponse(BaseModel):
    project_name: str
    run_id: str
    mix_wav_rel: str
    stems: List[RenderedStem]
    sample_rate: int = 44100
    duration_seconds: Optional[float] = None
