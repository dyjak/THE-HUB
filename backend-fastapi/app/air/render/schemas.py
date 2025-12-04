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
    # Opcjonalne dostrojenie voice-stealingu: długość fade-outu ogona
    # poprzedniej nuty w sekundach. 0.0 oznacza natychmiastowe ucięcie,
    # wartości rzędu 0.005-0.02 dają subtelne wygaszenie. Domyślnie 0.01s.
    fadeout_seconds: float = Field(0.01, ge=0.0, le=0.1)


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


class RecommendedSample(BaseModel):
    instrument: str
    sample_id: str
    path: Optional[str] = None
    # Inventory może zwracać root_midi jako float (z analizy FFT),
    # więc tutaj pozwalamy na dowolną wartość numeryczną.
    root_midi: Optional[float] = None
    gain_db_normalize: Optional[float] = None


class RecommendSamplesResponse(BaseModel):
    project_name: Optional[str] = None
    run_id: Optional[str] = None
    recommended_samples: Dict[str, RecommendedSample]
