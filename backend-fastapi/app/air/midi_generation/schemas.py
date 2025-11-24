from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional


class MidiMetaIn(BaseModel):
    """Minimalny podzbiór meta z param_generation potrzebny do komponowania MIDI.

    Oczekujemy, że frontend przekaże tutaj wprost `parsed.meta` z param_generation
    (lub bardzo zbliżoną strukturę).
    """

    style: str = Field(default="ambient")
    mood: str = Field(default="calm")
    tempo: int = Field(default=80, ge=20, le=300)
    key: str = Field(default="C")
    scale: str = Field(default="major")
    meter: str = Field(default="4/4")
    bars: int = Field(default=16, ge=1, le=512)
    length_seconds: float = Field(default=180.0, ge=30.0, le=3600.0)
    dynamic_profile: str = Field(default="moderate")
    arrangement_density: str = Field(default="balanced")
    harmonic_color: str = Field(default="diatonic")
    instruments: List[str] = Field(default_factory=list)
    instrument_configs: List[Dict[str, Any]] = Field(default_factory=list)
    seed: Optional[int] = None


class MidiGenerationIn(BaseModel):
    """Wejście do modułu midi_generation.

    Na ten moment zakładamy, że frontend przekazuje:
    - meta: to co dostał z param_generation (parsed.meta)
    - optionalnie provider/model dla AI-composera (domyślnie jak w param_generation)
    """

    meta: MidiMetaIn
    provider: Optional[str] = Field(default=None)
    model: Optional[str] = Field(default=None)
    # Opcjonalnie pozwalamy podać gotowe midi_json (np. do debugowania)
    ai_midi: Optional[Dict[str, Any]] = None


class MidiArtifactPaths(BaseModel):
    midi_json_rel: Optional[str] = None
    midi_mid_rel: Optional[str] = None
    midi_image_rel: Optional[str] = None


class MidiGenerationOut(BaseModel):
    run_id: str
    midi: Dict[str, Any]
    artifacts: MidiArtifactPaths
    provider: Optional[str] = None
    model: Optional[str] = None
    errors: Optional[List[str]] = None
    # Pełny kontekst wymiany z modelem (analogicznie do param_generation)
    system: Optional[str] = None
    user: Optional[str] = None
    raw: Optional[str] = None
    parsed: Optional[Dict[str, Any]] = None
