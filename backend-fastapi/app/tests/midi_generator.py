import os
import sys

import mido
from mido import MidiFile, MidiTrack, Message, MetaMessage
import random
from typing import Dict, List, Tuple
from dataclasses import dataclass

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')


@dataclass
class MusicParameters:
    """Parametry muzyczne zgodnie z dokumentacją AIR 4.0"""
    genre: str = "ambient"  # jazz, rock, techno, ambient
    mood: str = "peaceful"  # radosny, melancholijny, energetyczny, spokojny
    tempo: int = 60  # BPM
    key: str = "F"  # Tonacja
    scale: str = "major"  # major, minor
    rhythm: str = "simple"  # swing, prosty, synkopowany
    instruments: List[str] = None  # lista instrumentów

    def __post_init__(self):
        if self.instruments is None:
            self.instruments = ["piano", "strings", "pad"]


class MidiGenerator:
    """Generator MIDI zgodny z dokumentacją AIR 4.0"""

    # Mapowanie tonacji na nuty (MIDI note numbers)
    KEY_SIGNATURES = {
        "C": [60, 62, 64, 65, 67, 69, 71],  # C major
        "F": [65, 67, 69, 70, 72, 74, 76],  # F major
        "G": [67, 69, 71, 72, 74, 76, 78],  # G major
        "Am": [57, 59, 60, 62, 64, 65, 67],  # A minor
    }

    # Mapowanie instrumentów na MIDI channels
    INSTRUMENT_CHANNELS = {
        "piano": 0,
        "strings": 1,
        "pad": 2,
        "bass": 3,
        "drums": 9,  # Channel 9 for percussion
    }

    # MIDI Program Change dla instrumentów
    INSTRUMENT_PROGRAMS = {
        "piano": 0,  # Acoustic Grand Piano
        "strings": 48,  # String Ensemble 1
        "pad": 88,  # Pad 1 (new age)
        "bass": 32,  # Acoustic Bass
    }

    def __init__(self, parameters: MusicParameters):
        self.params = parameters
        self.midi_file = MidiFile()
        self.tracks = {}

    def generate_basic_track(self) -> MidiFile:
        """Generuje podstawowy utwór zgodnie z parametrami"""
        # Ustawienia tempo
        tempo = int(60000000 / self.params.tempo)  # Oblicz tempo manualnie

        for instrument in self.params.instruments:
            track = MidiTrack()
            self.midi_file.tracks.append(track)

            # Dodaj tempo do pierwszej ścieżki
            if len(self.midi_file.tracks) == 1:
                from mido import MetaMessage
                track.append(MetaMessage('set_tempo', tempo=tempo, time=0))

            # Program Change dla instrumentu
            if instrument in self.INSTRUMENT_PROGRAMS:
                channel = self.INSTRUMENT_CHANNELS.get(instrument, 0)
                track.append(Message('program_change',
                                     channel=channel,
                                     program=self.INSTRUMENT_PROGRAMS[instrument],
                                     time=0))

            # Generuj melodię dla instrumentu
            self._generate_melody_for_instrument(track, instrument)

        return self.midi_file

    def _generate_melody_for_instrument(self, track: MidiTrack, instrument: str):
        """Generuje melodię dla konkretnego instrumentu"""
        channel = self.INSTRUMENT_CHANNELS.get(instrument, 0)
        scale_notes = self.KEY_SIGNATURES.get(self.params.key, self.KEY_SIGNATURES["C"])

        # Długość utworu w taktach (4 takty = podstawowa struktura)
        bars = 8
        beats_per_bar = 4
        ticks_per_beat = 480  # Standard MIDI resolution

        current_time = 0

        if instrument == "pad":
            # Pad - długie akordy w tle
            self._generate_pad_chords(track, channel, scale_notes, bars, ticks_per_beat)
        elif instrument == "piano":
            # Piano - główna melodia
            self._generate_piano_melody(track, channel, scale_notes, bars, ticks_per_beat)
        elif instrument == "strings":
            # Strings - harmonia wspierająca
            self._generate_string_harmony(track, channel, scale_notes, bars, ticks_per_beat)

    def _generate_pad_chords(self, track: MidiTrack, channel: int, notes: List[int],
                             bars: int, ticks_per_beat: int):
        """Generuje długie akordy dla pada"""
        chord_duration = ticks_per_beat * 4  # Cały takt

        # Podstawowe akordy w tonacji
        chords = [
            [notes[0], notes[2], notes[4]],  # I
            [notes[3], notes[5], notes[0] + 12],  # IV
            [notes[4], notes[6], notes[1] + 12],  # V
            [notes[0], notes[2], notes[4]],  # I
        ]

        for bar in range(bars):
            chord = chords[bar % len(chords)]

            # Note ON dla wszystkich nut akordu
            for note in chord:
                track.append(Message('note_on', channel=channel, note=note, velocity=60, time=0))

            # Note OFF po długości akordu
            for i, note in enumerate(chord):
                time_offset = chord_duration if i == 0 else 0
                track.append(Message('note_off', channel=channel, note=note, velocity=0, time=time_offset))

    def _generate_piano_melody(self, track: MidiTrack, channel: int, notes: List[int],
                               bars: int, ticks_per_beat: int):
        """Generuje melodię dla pianina"""
        note_duration = ticks_per_beat // 2  # Ósemki

        for bar in range(bars):
            for beat in range(8):  # 8 ósemek na takt
                # Wybierz nutę ze skali
                note = random.choice(notes)
                if random.random() > 0.3:  # 70% szans na nutę
                    velocity = random.randint(50, 80)
                    track.append(Message('note_on', channel=channel, note=note, velocity=velocity, time=0))
                    track.append(Message('note_off', channel=channel, note=note, velocity=0, time=note_duration))
                else:
                    # Pauza
                    track.append(Message('note_off', channel=channel, note=60, velocity=0, time=note_duration))

    def _generate_string_harmony(self, track: MidiTrack, channel: int, notes: List[int],
                                 bars: int, ticks_per_beat: int):
        """Generuje harmonię dla sekcji smyczkowej"""
        note_duration = ticks_per_beat * 2  # Półnuty

        for bar in range(bars):
            for beat in range(2):  # 2 półnuty na takt
                # Wybierz 2-3 nuty do harmonii
                harmony_notes = random.sample(notes, random.randint(2, 3))

                # Note ON
                for note in harmony_notes:
                    track.append(Message('note_on', channel=channel, note=note + 12, velocity=45, time=0))

                # Note OFF
                for i, note in enumerate(harmony_notes):
                    time_offset = note_duration if i == 0 else 0
                    track.append(Message('note_off', channel=channel, note=note + 12, velocity=0, time=time_offset))

    def save_midi(self, filename: str):
        """Zapisuje wygenerowany MIDI do pliku"""
        import os
        output_dir = "output/midi"
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, filename)
        self.midi_file.save(filepath)
        print(f"MIDI saved to: {filepath}")


def test_basic_generation():
    """Test podstawowego generowania MIDI"""
    # Parametry zgodne z dokumentacją
    params = MusicParameters(
        genre="ambient",
        mood="peaceful",
        tempo=60,
        key="F",
        scale="major",
        instruments=["piano", "strings", "pad"]
    )

    generator = MidiGenerator(params)
    midi_file = generator.generate_basic_track()
    generator.save_midi("test_ambient_peaceful.mid")

    print("✅ Wygenerowano podstawowy utwór MIDI!")
    return midi_file


if __name__ == "__main__":
    test_basic_generation()