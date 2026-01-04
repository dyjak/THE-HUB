from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

# ten moduł zawiera schematy danych (pydantic) używane w kroku midi_generation.
#
# ogólny przepływ:
# - frontend wysyła `MidiGenerationIn` (meta z param_generation + opcjonalnie provider/model)
# - backend zwraca `MidiGenerationOut` (wygenerowane midi w json + ścieżki do artefaktów)


class MidiMetaIn(BaseModel):
    """minimalny podzbiór meta z param_generation potrzebny do komponowania midi.

    praktycznie frontend powinien tu przekazać to, co dostał w kroku 1 jako `parsed.meta`
    (albo strukturę bardzo zbliżoną).
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
    # opcjonalnie: oryginalny prompt użytkownika z kroku 1, przekazywany dla lepszego kontekstu
    user_prompt: Optional[str] = None
    instruments: List[str] = Field(default_factory=list)
    instrument_configs: List[Dict[str, Any]] = Field(default_factory=list)
    seed: Optional[int] = None


class MidiGenerationIn(BaseModel):
    """wejście do modułu midi_generation.

    zakładamy, że frontend przekazuje:
    - meta: dane z param_generation (najczęściej `parsed.meta`)
    - opcjonalnie: provider/model dla "ai kompozytora" (domyślnie jak w param_generation)
    """

    meta: MidiMetaIn
    provider: Optional[str] = Field(default=None)
    model: Optional[str] = Field(default=None)
    # opcjonalne powiązanie z run_id z param_generation (używane tylko do późniejszego eksportu).
    # to nie wpływa na strukturę plików wyjściowych midi.
    param_run_id: Optional[str] = Field(default=None)
    # opcjonalnie: pozwalamy wstrzyknąć gotowy midi_json (np. do debugowania i eksperymentów)
    ai_midi: Optional[Dict[str, Any]] = None


class MidiArtifactPaths(BaseModel):
    # ścieżki względne (względem katalogu `output/`) do artefaktów wygenerowanych na dysku
    midi_json_rel: Optional[str] = None
    midi_mid_rel: Optional[str] = None
    midi_image_rel: Optional[str] = None


class MidiGenerationOut(BaseModel):
    run_id: str
    midi: Dict[str, Any]
    artifacts: MidiArtifactPaths
    # opcjonalnie: wersje midi "per instrument" (osobny json/pianoroll dla każdego instrumentu)
    midi_per_instrument: Optional[Dict[str, Dict[str, Any]]] = None
    artifacts_per_instrument: Optional[Dict[str, MidiArtifactPaths]] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    errors: Optional[List[str]] = None
    # pełny kontekst wymiany z modelem (analogicznie do param_generation)
    system: Optional[str] = None
    user: Optional[str] = None
    raw: Optional[str] = None
    parsed: Optional[Dict[str, Any]] = None
