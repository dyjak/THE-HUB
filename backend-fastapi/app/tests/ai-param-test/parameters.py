from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import List, Literal, Dict, Any, Sequence

Style = Literal[
    "ambient", "jazz", "rock", "techno", "classical", "orchestral",
    "lofi", "hiphop", "house", "metal", "trap", "pop", "cinematic",
    "folk", "world", "experimental"
]
Mood = Literal[
    "calm", "energetic", "melancholic", "joyful", "mysterious",
    "epic", "relaxed", "aggressive", "dreamy", "groovy", "romantic",
    "dark", "uplifting", "serene", "tense"
]
Key = Literal[
    "C", "C#", "Db", "D", "D#", "Eb", "E", "F", "F#", "Gb", "G",
    "G#", "Ab", "A", "A#", "Bb", "B"
]
Scale = Literal[
    "major", "minor", "harmonic_minor", "melodic_minor", "dorian",
    "phrygian", "lydian", "mixolydian", "locrian", "pentatonic_major",
    "pentatonic_minor", "blues", "whole_tone", "phrygian_dominant",
    "hungarian_minor"
]
TimeSignature = Literal["4/4", "3/4", "6/8", "5/4", "7/8", "12/8"]
DynamicProfile = Literal["gentle", "moderate", "energetic"]
ArrangementDensity = Literal["minimal", "balanced", "dense"]
HarmonicColor = Literal["diatonic", "modal", "chromatic", "modulating", "experimental"]
Register = Literal["low", "mid", "high", "full"]
InstrumentRole = Literal["lead", "accompaniment", "rhythm", "pad", "bass", "percussion", "fx"]
Articulation = Literal["sustain", "staccato", "legato", "pizzicato", "accented", "slurred", "percussive", "glide", "arpeggiated"]
DynamicRange = Literal["delicate", "moderate", "intense"]

STYLE_OPTIONS: Sequence[str] = tuple(Style.__args__)  # type: ignore[attr-defined]
MOOD_OPTIONS: Sequence[str] = tuple(Mood.__args__)  # type: ignore[attr-defined]
TIME_SIGNATURE_OPTIONS: Sequence[str] = tuple(TimeSignature.__args__)  # type: ignore[attr-defined]
DYNAMIC_PROFILE_OPTIONS: Sequence[str] = tuple(DynamicProfile.__args__)  # type: ignore[attr-defined]
ARRANGEMENT_DENSITY_OPTIONS: Sequence[str] = tuple(ArrangementDensity.__args__)  # type: ignore[attr-defined]
HARMONIC_COLOR_OPTIONS: Sequence[str] = tuple(HarmonicColor.__args__)  # type: ignore[attr-defined]
REGISTER_OPTIONS: Sequence[str] = tuple(Register.__args__)  # type: ignore[attr-defined]
ROLE_OPTIONS: Sequence[str] = tuple(InstrumentRole.__args__)  # type: ignore[attr-defined]
ARTICULATION_OPTIONS: Sequence[str] = tuple(Articulation.__args__)  # type: ignore[attr-defined]
DYNAMIC_RANGE_OPTIONS: Sequence[str] = tuple(DynamicRange.__args__)  # type: ignore[attr-defined]
KEY_OPTIONS: Sequence[str] = tuple(Key.__args__)  # type: ignore[attr-defined]
SCALE_OPTIONS: Sequence[str] = tuple(Scale.__args__)  # type: ignore[attr-defined]
EFFECT_OPTIONS: Sequence[str] = (
    "reverb", "delay", "chorus", "distortion", "filter", "compression",
    "phaser", "flanger", "shimmer", "lofi"
)
DEFAULT_FORM: List[str] = [
    "intro", "verse", "chorus", "verse", "chorus", "bridge", "chorus", "outro"
]
DEFAULT_INSTRUMENTS: List[str] = ["piano", "pad", "strings"]


def _ensure_choice(value: Any, options: Sequence[str], default: str) -> str:
    """Case-insensitive choice helper that gracefully falls back."""
    if not value:
        return default
    text = str(value).strip()
    if not text:
        return default
    if text in options:
        return text
    lower = text.lower()
    for opt in options:
        if lower == opt.lower():
            return opt
    return default


def _sanitize_list(values: Any) -> List[str]:
    items: List[str] = []
    if isinstance(values, (list, tuple, set)):
        source = values
    elif isinstance(values, str):
        source = values.split(",")
    else:
        return items
    seen = set()
    for raw in source:
        text = str(raw).strip()
        if text and text not in seen:
            seen.add(text)
            items.append(text)
    return items


def _default_form() -> List[str]:
    return list(DEFAULT_FORM)


def _default_instruments() -> List[str]:
    return list(DEFAULT_INSTRUMENTS)


@dataclass
class InstrumentParameters:
    name: str
    register: Register = "mid"
    role: InstrumentRole = "accompaniment"
    volume: float = 0.8
    pan: float = 0.0
    articulation: Articulation = "sustain"
    dynamic_range: DynamicRange = "moderate"
    effects: List[str] = field(default_factory=list)

    def validate(self) -> "InstrumentParameters":
        self.name = str(self.name).strip()
        if not self.name:
            raise ValueError("instrument name cannot be empty")
        try:
            self.volume = float(self.volume)
        except Exception:
            self.volume = 0.8
        self.volume = max(0.0, min(1.0, self.volume))
        try:
            self.pan = float(self.pan)
        except Exception:
            self.pan = 0.0
        self.pan = max(-1.0, min(1.0, self.pan))
        self.register = _ensure_choice(self.register, REGISTER_OPTIONS, "mid")  # type: ignore[arg-type]
        self.role = _ensure_choice(self.role, ROLE_OPTIONS, "accompaniment")  # type: ignore[arg-type]
        self.articulation = _ensure_choice(self.articulation, ARTICULATION_OPTIONS, "sustain")  # type: ignore[arg-type]
        self.dynamic_range = _ensure_choice(self.dynamic_range, DYNAMIC_RANGE_OPTIONS, "moderate")  # type: ignore[arg-type]
        if not isinstance(self.effects, list):
            self.effects = []
        cleaned: List[str] = []
        seen = set()
        for effect in self.effects:
            text = str(effect).strip()
            if not text:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            if text in EFFECT_OPTIONS:
                cleaned.append(text)
            else:
                cleaned.append(text)
        self.effects = cleaned
        return self


def create_default_instrument_config(name: str, idx: int = 0) -> InstrumentParameters:
    lower = name.lower()
    register: Register = "mid"
    role: InstrumentRole = "accompaniment"
    articulation: Articulation = "sustain"
    dynamic_range: DynamicRange = "moderate"
    effects: List[str] = ["reverb"]
    volume = 0.8
    pan = max(-0.6, min(0.6, -0.2 + idx * 0.3))

    if lower in {"bass", "bass_synth", "bass_guitar", "808", "reese"}:
        register = "low"
        role = "bass"
        dynamic_range = "intense"
        articulation = "legato"
        effects = ["compression", "filter"]
        volume = 0.9
        pan = 0.0
    elif lower in {"kick", "snare", "hihat", "clap", "perc", "drumkit", "tom"}:
        register = "low"
        role = "percussion"
        dynamic_range = "intense"
        articulation = "percussive"
        effects = ["compression"]
        volume = 0.95
        pan = 0.0
    elif lower in {"pad", "strings", "choir"}:
        register = "full"
        role = "pad"
        dynamic_range = "moderate"
        articulation = "sustain"
        effects = ["reverb", "chorus"]
        volume = 0.85
    elif lower in {"lead", "synth", "guitar", "piano", "flute", "trumpet", "saxophone"}:
        role = "lead" if idx == 0 else "accompaniment"
        register = "mid" if lower not in {"flute"} else "high"
        articulation = "legato" if lower in {"synth", "flute"} else "sustain"
        effects = ["reverb", "delay"]
        volume = 0.9 if role == "lead" else 0.8
    else:
        role = "lead" if idx == 0 else "accompaniment"
        volume = 0.85 if role == "lead" else 0.75

    config = InstrumentParameters(
        name=name,
        register=register,
        role=role,
        volume=volume,
        pan=pan,
        articulation=articulation,
        dynamic_range=dynamic_range,
        effects=effects,
    )
    return config.validate()


def _default_instrument_configs() -> List[InstrumentParameters]:
    return [create_default_instrument_config(inst, idx) for idx, inst in enumerate(DEFAULT_INSTRUMENTS)]


@dataclass
class MidiParameters:
    style: Style = "ambient"
    mood: Mood = "calm"
    tempo: int = 80
    key: Key = "C"
    scale: Scale = "major"
    meter: TimeSignature = "4/4"
    bars: int = 16
    length_seconds: float = 180.0
    form: List[str] = field(default_factory=_default_form)
    dynamic_profile: DynamicProfile = "moderate"
    arrangement_density: ArrangementDensity = "balanced"
    harmonic_color: HarmonicColor = "diatonic"
    instruments: List[str] = field(default_factory=_default_instruments)
    instrument_configs: List[InstrumentParameters] = field(default_factory=_default_instrument_configs)
    seed: int | None = None

    def validate(self) -> "MidiParameters":
        try:
            self.tempo = int(self.tempo)
        except Exception:
            self.tempo = 80
        self.tempo = max(20, min(300, self.tempo))

        self.key = _ensure_choice(self.key, KEY_OPTIONS, "C")  # type: ignore[arg-type]
        self.scale = _ensure_choice(self.scale, SCALE_OPTIONS, "major")  # type: ignore[arg-type]
        self.style = _ensure_choice(self.style, STYLE_OPTIONS, "ambient")  # type: ignore[arg-type]
        self.mood = _ensure_choice(self.mood, MOOD_OPTIONS, "calm")  # type: ignore[arg-type]
        self.meter = _ensure_choice(self.meter, TIME_SIGNATURE_OPTIONS, "4/4")  # type: ignore[arg-type]
        self.dynamic_profile = _ensure_choice(self.dynamic_profile, DYNAMIC_PROFILE_OPTIONS, "moderate")  # type: ignore[arg-type]
        self.arrangement_density = _ensure_choice(self.arrangement_density, ARRANGEMENT_DENSITY_OPTIONS, "balanced")  # type: ignore[arg-type]
        self.harmonic_color = _ensure_choice(self.harmonic_color, HARMONIC_COLOR_OPTIONS, "diatonic")  # type: ignore[arg-type]

        try:
            self.bars = int(self.bars)
        except Exception:
            self.bars = 16
        self.bars = max(1, min(512, self.bars))

        try:
            self.length_seconds = float(self.length_seconds)
        except Exception:
            self.length_seconds = 180.0
        self.length_seconds = max(30.0, min(3600.0, self.length_seconds))

        cleaned_form = _sanitize_list(self.form)
        self.form = cleaned_form or _default_form()

        instruments = _sanitize_list(self.instruments)
        self.instruments = instruments or _default_instruments()

        configs: Dict[str, InstrumentParameters] = {}
        for item in self.instrument_configs:
            cfg: InstrumentParameters
            if isinstance(item, InstrumentParameters):
                cfg = item
            elif isinstance(item, dict):
                cfg = InstrumentParameters(
                    name=item.get("name", ""),
                    register=item.get("register", "mid"),
                    role=item.get("role", "accompaniment"),
                    volume=item.get("volume", 0.8),
                    pan=item.get("pan", 0.0),
                    articulation=item.get("articulation", "sustain"),
                    dynamic_range=item.get("dynamic_range", "moderate"),
                    effects=item.get("effects", []),
                )
            else:
                continue
            try:
                configs[cfg.name] = cfg.validate()
            except ValueError:
                continue

        for idx, inst in enumerate(self.instruments):
            if inst not in configs:
                configs[inst] = create_default_instrument_config(inst, idx)

        self.instrument_configs = [configs[name] for name in self.instruments]

        if self.seed == "":  # type: ignore[comparison-overlap]
            self.seed = None
        if self.seed is not None:
            try:
                self.seed = int(self.seed)
            except Exception:
                self.seed = None

        return self

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["genre"] = data.get("style")  # legacy alias for UI convenience
        return data

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "MidiParameters":
        midi = MidiParameters(
            style=data.get("style") or data.get("genre") or "ambient",
            mood=data.get("mood", "calm"),
            tempo=data.get("tempo", 80),
            key=data.get("key", "C"),
            scale=data.get("scale", "major"),
            meter=data.get("meter", "4/4"),
            bars=data.get("bars", 16),
            length_seconds=data.get("length_seconds", 180.0),
            form=data.get("form") or _default_form(),
            dynamic_profile=data.get("dynamic_profile", "moderate"),
            arrangement_density=data.get("arrangement_density", "balanced"),
            harmonic_color=data.get("harmonic_color", "diatonic"),
            instruments=data.get("instruments") or _default_instruments(),
            instrument_configs=data.get("instrument_configs") or _default_instrument_configs(),
            seed=data.get("seed"),
        )
        return midi.validate()


@dataclass
class AudioRenderParameters:
    sample_rate: int = 44100
    seconds: float = 6.0
    master_gain_db: float = -3.0

    def validate(self) -> "AudioRenderParameters":
        if not 8000 <= self.sample_rate <= 192000:
            raise ValueError("Unsupported sample rate")
        if not 0.5 <= self.seconds <= 600:
            raise ValueError("seconds out of range")
        return self

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, Any] | None) -> "AudioRenderParameters":
        payload = data or {}
        params = AudioRenderParameters(
            sample_rate=payload.get("sample_rate", 44100),
            seconds=payload.get("seconds", 6.0),
            master_gain_db=payload.get("master_gain_db", -3.0),
        )
        return params.validate()


def preset_minimal() -> Dict[str, Any]:
    midi = MidiParameters(
        style="ambient",
        mood="calm",
        tempo=72,
        key="C",
        scale="major",
        meter="4/4",
        bars=16,
        length_seconds=120.0,
        form=["intro", "verse", "chorus", "outro"],
        dynamic_profile="gentle",
        arrangement_density="minimal",
        harmonic_color="diatonic",
        instruments=["piano"],
        instrument_configs=[create_default_instrument_config("piano")],
    ).validate()
    return {
        "midi": midi.to_dict(),
        "audio": AudioRenderParameters(seconds=3.0).to_dict(),
    }


def preset_full() -> Dict[str, Any]:
    midi = MidiParameters().validate()
    return {
        "midi": midi.to_dict(),
        "audio": AudioRenderParameters().to_dict(),
    }


PRESETS = {"minimal": preset_minimal, "full": preset_full}
