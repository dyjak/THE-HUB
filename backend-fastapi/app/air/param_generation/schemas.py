from __future__ import annotations
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any


INSTRUMENT_OPTIONS = [
    "piano","pad","strings","bass","guitar","lead","choir","flute","trumpet","saxophone",
    "kick","snare","hihat","clap","rim","tom","808","perc","drumkit","fx"
]

# Dynamically extend instrument list from inventory if available (future-proof for new types)
try:  # pragma: no cover runtime presence
    from app.air.inventory.access import list_instruments as _inv_list
    _extra = [i for i in _inv_list() if i not in INSTRUMENT_OPTIONS]
    if _extra:
        INSTRUMENT_OPTIONS.extend(_extra)
except Exception:
    pass


class InstrumentConfig(BaseModel):
    name: str
    role: str = Field(default="accompaniment")
    register: str = Field(default="mid")
    volume: float = Field(ge=0, le=1, default=0.8)
    pan: float = Field(ge=-1, le=1, default=0.0)
    articulation: str = Field(default="sustain")
    dynamic_range: str = Field(default="moderate")


class MidiPlanIn(BaseModel):
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
    seed: Optional[int] = None

    @validator("instruments", pre=True)
    def normalize_instruments(cls, v):
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
            # Allow passthrough if present in dynamic inventory; otherwise require INSTRUMENT_OPTIONS
            if name not in INSTRUMENT_OPTIONS:
                continue
            if name not in seen:
                seen.add(name)
                out.append(name)
        return out or ["piano","pad","strings"]

    @validator("instrument_configs", always=True)
    def ensure_configs(cls, v, values):
        instruments: List[str] = values.get("instruments", [])
        mapped = {c.name: c for c in v} if v else {}
        out: List[InstrumentConfig] = []
        for idx, inst in enumerate(instruments):
            existing = mapped.get(inst)
            if existing:
                out.append(existing)
                continue
            # create default
            role = "lead" if idx == 0 else "accompaniment"
            register = "low" if inst in ("bass","808") else "mid"
            out.append(InstrumentConfig(name=inst, role=role, register=register))
        return out

    def to_payload(self) -> Dict[str, Any]:
        return self.dict()


class MidiPlanResult(BaseModel):
    run_id: str
    plan: Dict[str, Any]
    raw: str
    parsed: Dict[str, Any] | None = None
    errors: List[str] | None = None
    meta: Dict[str, Any] | None = None
    saved_json_rel: str | None = None
    saved_raw_rel: str | None = None
