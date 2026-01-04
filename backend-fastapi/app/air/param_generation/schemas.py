from __future__ import annotations
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any

# ten moduł definiuje schematy danych (pydantic), które opisują wejście i wyjście
# dla kroku "planowania parametrów".
#
# w skrócie:
# - `ParameterPlanIn` to dane, które frontend wysyła do backendu (prompt + ustawienia bazowe)
# - walidatory normalizują listę instrumentów i tworzą brakujące `instrument_configs`
# - `ParameterPlanResult` to wynik zwracany do frontendu (surowa odpowiedź llm + sparsowane json)


INSTRUMENT_OPTIONS = [
    "piano","pad","strings","bass","guitar","lead","choir","flute","trumpet","saxophone",
    "kick","snare","hihat","clap","rim","tom","808","perc","drumkit","fx"
]

# dynamiczne rozszerzenie listy instrumentów na podstawie inventory (jeśli jest dostępne).
# chodzi o to, aby nowe typy instrumentów dodane w inventory były od razu akceptowane przez api,
# bez ręcznego dopisywania ich do stałej `INSTRUMENT_OPTIONS`.
try:  # pragma: no cover runtime presence
    from app.air.inventory.access import list_instruments as _inv_list
    _extra = [i for i in _inv_list() if i not in INSTRUMENT_OPTIONS]
    if _extra:
        INSTRUMENT_OPTIONS.extend(_extra)
except Exception:
    pass


class InstrumentConfig(BaseModel):
    # konfiguracja jednego instrumentu w aranżacji.
    # frontend może doprecyzować rolę/brzmienie, a backend przechowuje to razem z planem.
    name: str
    role: str = Field(default="accompaniment")
    register: str = Field(default="mid")
    articulation: str = Field(default="sustain")
    dynamic_range: str = Field(default="moderate")


class ParameterPlanIn(BaseModel):
    # opis użytkownika w języku naturalnym, np. "filmowa muzyka z gitarą basową".
    # to jest główne wejście dla llm, które ma zaplanować parametry muzyczne.
    prompt: str = Field(default="")
    style: str = Field(default="ambient")
    mood: str = Field(default="calm")
    tempo: int = Field(default=80, ge=20, le=300)
    key: str = Field(default="C")
    scale: str = Field(default="major")
    meter: str = Field(default="4/4")
    bars: int = Field(default=16, ge=1, le=512)
    length_seconds: int = Field(default=180, ge=30, le=3600)
    dynamic_profile: str = Field(default="moderate")
    arrangement_density: str = Field(default="balanced")
    harmonic_color: str = Field(default="diatonic")
    instruments: List[str] = Field(default_factory=lambda: ["piano","pad","strings"])
    instrument_configs: List[InstrumentConfig] = Field(default_factory=list)

    @validator("instruments", pre=True)
    def normalize_instruments(cls, v):
        # normalizacja pola `instruments`:
        # - wspieramy format string ("piano,pad,strings") i listę
        # - usuwamy białe znaki, duplikaty i nieprawidłowe wartości
        # - filtrujemy tylko do instrumentów, które są dozwolone (stała + inventory)
        # - jeśli po filtracji nic nie zostało, ustawiamy bezpieczne domyślne trio
        if isinstance(v, str):
            v = [x.strip() for x in v.split(",") if x.strip()]
        if not isinstance(v, list):
            return []
        out: List[str] = []
        seen: set[str] = set()
        for item in v:
            if not isinstance(item, str):
                continue
            name = item.strip()
            if not name:
                continue
            # przepuszczamy tylko instrumenty, które występują w dozwolonej liście
            if name not in INSTRUMENT_OPTIONS:
                continue
            if name not in seen:
                seen.add(name)
                out.append(name)
        return out or ["piano","pad","strings"]

    @validator("instrument_configs", always=True)
    def ensure_configs(cls, v, values):
        # upewniamy się, że `instrument_configs` jest spójne z listą `instruments`.
        # jeśli frontend nie przysłał konfiguracji dla któregoś instrumentu,
        # tworzymy domyślny `InstrumentConfig` (z prostą heurystyką dla roli/rejestru).
        instruments: List[str] = values.get("instruments", [])
        mapped = {c.name: c for c in v} if v else {}
        out: List[InstrumentConfig] = []
        for idx, inst in enumerate(instruments):
            existing = mapped.get(inst)
            if existing:
                out.append(existing)
                continue
            # tworzenie konfiguracji domyślnej
            role = "lead" if idx == 0 else "accompaniment"
            register = "low" if inst in ("bass","808") else "mid"
            out.append(InstrumentConfig(name=inst, role=role, register=register))
        return out

    def to_payload(self) -> Dict[str, Any]:
        # pomocnicza serializacja do słownika (np. do przekazania dalej w pipeline)
        return self.dict()


class ParameterPlanResult(BaseModel):
    # wynik kroku planowania parametrów (z backendu do frontendu).
    # `raw` to surowy tekst z llm, a `parsed` to (jeśli się udało) sparsowany obiekt json.
    run_id: str
    plan: Dict[str, Any]
    raw: str
    parsed: Dict[str, Any] | None = None
    errors: List[str] | None = None
    meta: Dict[str, Any] | None = None
    saved_json_rel: str | None = None
    saved_raw_rel: str | None = None
    # mapowanie: instrument -> id sampla z inventory wybrany w ui.
    # to nie jest część logiki llm; służy do spięcia instrumentów z konkretnymi plikami audio.
    selected_samples: Dict[str, str] | None = None
