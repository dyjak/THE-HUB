from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import List, Literal, Dict, Any

Genre = Literal[
    "ambient", "jazz", "rock", "techno", "classical",
    "orchestral", "lofi", "hiphop", "house", "metal"
]
Mood = Literal[
    "calm", "energetic", "melancholic", "joyful", "mysterious",
    "epic", "relaxed", "aggressive", "dreamy", "groovy", "romantic"
]
Key = Literal["C", "A", "F", "D", "G"]
Scale = Literal["major", "minor"]


@dataclass
class MidiParameters:
    genre: Genre = "ambient"
    mood: Mood = "calm"
    tempo: int = 80
    key: Key = "C"
    scale: Scale = "major"
    instruments: List[str] = field(default_factory=lambda: ["piano", "pad", "strings"])
    bars: int = 8
    seed: int | None = None

    def validate(self):
        if not 40 <= self.tempo <= 240:
            raise ValueError("tempo out of range (40-240)")
        if self.bars < 1 or self.bars > 128:
            raise ValueError("bars out of range (1-128)")
        return self

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AudioRenderParameters:
    sample_rate: int = 44100
    seconds: float = 6.0
    master_gain_db: float = -3.0

    def validate(self):
        if not 8000 <= self.sample_rate <= 192000:
            raise ValueError("Unsupported sample rate")
        if not 0.5 <= self.seconds <= 600:
            raise ValueError("seconds out of range")
        return self

    def to_dict(self):
        return asdict(self)


def preset_minimal() -> Dict[str, Any]:
    return {
        "midi": MidiParameters(bars=4, instruments=["piano"]).to_dict(),
        "audio": AudioRenderParameters(seconds=3.0).to_dict(),
    }


def preset_full() -> Dict[str, Any]:
    return {
        "midi": MidiParameters().to_dict(),
        "audio": AudioRenderParameters().to_dict(),
    }


PRESETS = {"minimal": preset_minimal, "full": preset_full}
