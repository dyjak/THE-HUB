from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional


class TrackEQ(BaseModel):
    low: float = Field(0.0, description="Low shelf gain in dB")
    mid: float = Field(0.0, description="Mid band gain in dB")
    high: float = Field(0.0, description="High shelf gain in dB")


class TrackCompressor(BaseModel):
    threshold: float = Field(-18.0, description="Threshold in dB")
    ratio: float = Field(2.0, description="Compression ratio")


class TrackReverb(BaseModel):
    mix: float = Field(0.15, ge=0.0, le=1.0, description="Wet mix (0-1)")
    time: float = Field(1.5, ge=0.1, le=10.0, description="Decay time in seconds")


class TrackDelay(BaseModel):
    mix: float = Field(0.1, ge=0.0, le=1.0, description="Wet mix (0-1)")
    time_ms: float = Field(400.0, ge=50.0, le=2000.0, description="Delay time in ms")
    feedback: float = Field(0.3, ge=0.0, le=0.95, description="Feedback amount (0-0.95)")


class TrackSettings(BaseModel):
    instrument: str
    enabled: bool = True
    volume_db: float = Field(0.0, ge=-60.0, le=6.0)
    pan: float = Field(0.0, ge=-1.0, le=1.0, description="-1 = left, 0 = center, 1 = right")
    eq: TrackEQ = Field(default_factory=TrackEQ)
    comp: TrackCompressor = Field(default_factory=TrackCompressor)
    reverb: TrackReverb = Field(default_factory=TrackReverb)
    delay: TrackDelay = Field(default_factory=TrackDelay)


class RenderRequest(BaseModel):
    """Request payload for audio rendering step.

    For now we keep DSP simple: volume + pan are applied,
    while EQ/comp/reverb/delay are accepted for future use
    without breaking the schema.
    """

    project_name: str = Field(..., min_length=1, max_length=200)
    run_id: str = Field(..., min_length=1)
    midi: Dict[str, Any]
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
