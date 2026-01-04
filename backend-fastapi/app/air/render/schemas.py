from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional

# ten moduł zawiera schematy danych (pydantic) dla kroku render.
#
# render w tym projekcie oznacza "złożenie audio": na podstawie midi i wybranych sampli
# generujemy pliki wav (mix oraz stem-y per instrument).


class TrackSettings(BaseModel):
    # ustawienia pojedynczego toru (instrumentu) w renderze
    instrument: str
    enabled: bool = True
    volume_db: float = Field(0.0, ge=-60.0, le=6.0)
    pan: float = Field(0.0, ge=-1.0, le=1.0, description="-1 = left, 0 = center, 1 = right")


class RenderRequest(BaseModel):
    """payload żądania dla kroku render (generowanie audio).

    na ten moment renderer realnie używa przede wszystkim:
    - `tracks` (volume_db i pan),
    - `selected_samples` (jakie sample mają grać),
    - `midi` / `midi_per_instrument` (gdzie i jakie eventy mają wystąpić).
    """

    project_name: str = Field(..., min_length=1, max_length=200)
    run_id: str = Field(..., min_length=1)
    # opcjonalnie: identyfikator użytkownika przekazywany z frontendu (nextauth)
    user_id: Optional[int] = None
    midi: Dict[str, Any]
    # opcjonalnie: pełny podział midi per instrument z modułu midi_generation
    midi_per_instrument: Dict[str, Dict[str, Any]] | None = None
    tracks: List[TrackSettings]
    # mapowanie: instrument -> id sampla z inventory (row.id) albo bezpośrednia ścieżka
    selected_samples: Dict[str, str] | None = None
    # opcjonalne dostrojenie "voice stealingu": długość fade-outu ogona poprzedniej nuty.
    # jednostka: sekundy.
    # - 0.0 oznacza natychmiastowe ucięcie
    # - wartości rzędu 0.005-0.02 dają subtelne wygaszenie
    # domyślnie: 0.01 s
    fadeout_seconds: float = Field(0.01, ge=0.0, le=0.1)


class RenderedStem(BaseModel):
    # opis pojedynczego stem-a (osobnego pliku wav dla instrumentu)
    instrument: str
    audio_rel: str


class RenderResponse(BaseModel):
    # odpowiedź renderu: mix + lista stemów
    project_name: str
    run_id: str
    mix_wav_rel: str
    stems: List[RenderedStem]
    sample_rate: int = 44100
    duration_seconds: Optional[float] = None


class RecommendedSample(BaseModel):
    # pojedyncza rekomendacja sampla (podpowiedź dla ui)
    instrument: str
    sample_id: str
    path: Optional[str] = None
    # inventory może zwracać root_midi jako float (z analizy fft),
    # więc tutaj pozwalamy na dowolną wartość numeryczną
    root_midi: Optional[float] = None
    gain_db_normalize: Optional[float] = None


class RecommendSamplesResponse(BaseModel):
    # odpowiedź endpointu rekomendacji sampli
    project_name: Optional[str] = None
    run_id: Optional[str] = None
    recommended_samples: Dict[str, RecommendedSample]
