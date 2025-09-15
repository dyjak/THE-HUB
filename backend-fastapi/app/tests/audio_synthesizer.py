import sys

import mido
import numpy as np
from typing import Dict, List, Tuple
import os
from dataclasses import dataclass
from sample_fetcher import SampleFetcher, SampleInfo

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')




@dataclass
class AudioSettings:
    """Ustawienia audio dla syntezy"""
    sample_rate: int = 44100
    bit_depth: int = 16
    channels: int = 2  # Stereo
    buffer_size: int = 1024


class SimpleSynthesizer:
    """Prosty syntezator do konwersji MIDI na audio"""

    def __init__(self, settings: AudioSettings = None):
        self.settings = settings or AudioSettings()
        self.sample_fetcher = SampleFetcher()
        self.loaded_samples = {}

        # Podstawowe częstotliwości nut (MIDI note number -> Hz)
        self.note_frequencies = self._generate_note_frequencies()

    def _generate_note_frequencies(self) -> Dict[int, float]:
        """Generuje mapowanie MIDI note number -> częstotliwość"""
        frequencies = {}
        # A4 (MIDI note 69) = 440 Hz
        for midi_note in range(128):
            frequencies[midi_note] = 440.0 * (2 ** ((midi_note - 69) / 12.0))
        return frequencies

    def load_samples_for_instruments(self, instruments: List[str], genre: str = "ambient"):
        """Ładuje sample dla instrumentów"""
        print(f"🎼 Loading samples for instruments: {instruments}")

        genre_samples = self.sample_fetcher.get_samples_for_genre(genre)

        for instrument in instruments:
            if instrument in genre_samples:
                samples = genre_samples[instrument]
                if samples:
                    # Użyj pierwszego dostępnego sampla dla instrumentu
                    sample = samples[0]
                    sample_path = self.sample_fetcher.download_sample(sample)
                    self.loaded_samples[instrument] = {
                        'info': sample,
                        'path': sample_path,
                        'audio_data': self._load_audio_data(sample_path)
                    }
                    print(f"  ✅ Loaded {instrument}: {sample.name}")
                else:
                    print(f"  ⚠️  No samples found for {instrument}")
            else:
                print(f"  ⚠️  No samples available for {instrument}")

    def _load_audio_data(self, file_path: str) -> np.ndarray:
        """Ładuje dane audio z pliku"""
        try:
            from scipy.io.wavfile import read
            sample_rate, audio_data = read(file_path)

            # Konwertuj na float i znormalizuj
            if audio_data.dtype == np.int16:
                audio_data = audio_data.astype(np.float32) / 32768.0
            elif audio_data.dtype == np.int32:
                audio_data = audio_data.astype(np.float32) / 2147483648.0

            # Jeśli stereo, weź lewą ścieżkę
            if len(audio_data.shape) > 1:
                audio_data = audio_data[:, 0]

            # Ogranicz długość
            if len(audio_data) > 44100 * 5:  # Max 5 sekund
                audio_data = audio_data[:44100 * 5]

            return audio_data

        except ImportError:
            print("⚠️  scipy not available, generating sine wave")
            duration = 2.0
            t = np.linspace(0, duration, int(self.settings.sample_rate * duration))
            return np.sin(2 * np.pi * 440 * t) * 0.3
        except Exception as e:
            print(f"⚠️  Error loading audio: {e}, generating sine wave")
            duration = 2.0
            t = np.linspace(0, duration, int(self.settings.sample_rate * duration))
            return np.sin(2 * np.pi * 440 * t) * 0.3

    def synthesize_midi_to_audio(self, midi_file_path: str, output_path: str = None) -> str:
        """Konwertuje plik MIDI na audio"""
        if output_path is None:
            output_path = midi_file_path.replace('.mid', '.wav').replace('/midi/', '/audio/')

        # Upewnij się, że katalog istnieje
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        print(f"🎵 Synthesizing MIDI to audio...")
        print(f"  Input: {midi_file_path}")
        print(f"  Output: {output_path}")

        # Ładuj plik MIDI
        midi_file = mido.MidiFile(midi_file_path)

        # Analizuj MIDI i wygeneruj audio
        audio_tracks = self._process_midi_tracks(midi_file)

        # Miksal ścieżki
        final_audio = self._mix_tracks(audio_tracks)

        # Zapisz do pliku
        self._save_audio(final_audio, output_path)

        print(f"  ✅ Audio saved to: {output_path}")
        return output_path

    def _process_midi_tracks(self, midi_file: mido.MidiFile) -> List[np.ndarray]:
        """Przetwarza ścieżki MIDI na audio"""
        audio_tracks = []

        # Oblicz całkowitą długość w sekundach
        total_time = 0
        for track in midi_file.tracks:
            track_time = 0
            for msg in track:
                track_time += msg.time
            total_time = max(total_time, track_time)

        # Konwertuj z ticks na sekundy
        ticks_per_beat = midi_file.ticks_per_beat
        tempo = 500000  # Default tempo (120 BPM)

        # Znajdź tempo w pierwszej ścieżce
        for track in midi_file.tracks:
            for msg in track:
                if msg.type == 'set_tempo':
                    tempo = msg.tempo
                    break
            break

        seconds_per_tick = (tempo / 1000000.0) / ticks_per_beat
        total_duration = total_time * seconds_per_tick

        # Utwórz bufor audio dla każdej ścieżki
        total_samples = int(total_duration * self.settings.sample_rate)

        for track_idx, track in enumerate(midi_file.tracks):
            print(f"  Processing track {track_idx + 1}/{len(midi_file.tracks)}")

            # Utwórz pusty bufor audio dla tej ścieżki
            track_audio = np.zeros(total_samples)

            # Śledź aktywne nuty
            active_notes = {}
            current_time_ticks = 0
            current_instrument = "piano"  # Default

            for msg in track:
                current_time_ticks += msg.time
                current_time_seconds = current_time_ticks * seconds_per_tick
                current_sample = int(current_time_seconds * self.settings.sample_rate)

                if msg.type == 'program_change':
                    # Mapuj program change na instrument
                    current_instrument = self._map_program_to_instrument(msg.program)

                elif msg.type == 'note_on' and msg.velocity > 0:
                    # Rozpocznij nutę
                    note_audio = self._generate_note_audio(
                        msg.note,
                        msg.velocity,
                        current_instrument,
                        duration=2.0  # Default duration
                    )

                    # Dodaj do bufora ścieżki
                    end_sample = min(current_sample + len(note_audio), len(track_audio))
                    actual_length = end_sample - current_sample
                    if actual_length > 0:
                        track_audio[current_sample:end_sample] += note_audio[:actual_length]

                elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                    # Zakończ nutę (w prostej implementacji ignorujemy)
                    pass

            # Normalizuj ścieżkę
            if np.max(np.abs(track_audio)) > 0:
                track_audio = track_audio / np.max(np.abs(track_audio)) * 0.8

            audio_tracks.append(track_audio)

        return audio_tracks

    def _map_program_to_instrument(self, program: int) -> str:
        """Mapuje MIDI program number na instrument"""
        if program == 0:
            return "piano"
        elif 48 <= program <= 55:
            return "strings"
        elif 88 <= program <= 95:
            return "pad"
        elif 32 <= program <= 39:
            return "bass"
        else:
            return "piano"

    def _generate_note_audio(self, midi_note: int, velocity: int, instrument: str, duration: float) -> np.ndarray:
        """Generuje audio dla pojedynczej nuty"""
        frequency = self.note_frequencies[midi_note]
        sample_rate = self.settings.sample_rate
        t = np.linspace(0, duration, int(sample_rate * duration))
        amplitude = velocity / 127.0

        # Sprawdź czy mamy załadowany sample dla instrumentu
        if instrument in self.loaded_samples:
            # Użyj prawdziwego sampla
            sample_data = self.loaded_samples[instrument]['audio_data']

            # Proste pitch shifting (nie idealne, ale działa)
            # Przeskaluj sample według częstotliwości
            base_freq = 261.63  # C4
            pitch_ratio = frequency / base_freq

            # Zmień długość sampla według pitch ratio
            new_length = int(len(sample_data) / pitch_ratio)
            if new_length > 0 and new_length < len(sample_data) * 4:
                # Resample (prosty sposób)
                indices = np.linspace(0, len(sample_data) - 1, new_length)
                pitched_sample = np.interp(indices, range(len(sample_data)), sample_data)
            else:
                pitched_sample = sample_data

            # Dopasuj długość do żądanej duration
            target_length = len(t)
            if len(pitched_sample) > target_length:
                audio = pitched_sample[:target_length]
            else:
                # Zapętl sample jeśli jest za krótki
                repeats = (target_length // len(pitched_sample)) + 1
                extended = np.tile(pitched_sample, repeats)
                audio = extended[:target_length]

            # Zastosuj amplitude
            audio = audio * amplitude

        else:
            # Fallback: generuj syntezowane audio
            if instrument == "piano":
                # Piano - harmonic-rich sound
                audio = (np.sin(2 * np.pi * frequency * t) * 0.6 +
                         np.sin(2 * np.pi * frequency * 2 * t) * 0.3 +
                         np.sin(2 * np.pi * frequency * 3 * t) * 0.1)

                # ADSR envelope dla pianina
                attack = int(0.01 * sample_rate)  # 10ms attack
                decay = int(0.3 * sample_rate)  # 300ms decay
                sustain_level = 0.7
                release = int(0.5 * sample_rate)  # 500ms release

                envelope = np.ones_like(audio)
                if len(envelope) > attack:
                    envelope[:attack] = np.linspace(0, 1, attack)
                if len(envelope) > attack + decay:
                    envelope[attack:attack + decay] = np.linspace(1, sustain_level, decay)
                if len(envelope) > release:
                    envelope[-release:] = np.linspace(sustain_level, 0, release)

                audio *= envelope

            elif instrument == "strings":
                # Strings - smooth, rich harmonics
                audio = (np.sin(2 * np.pi * frequency * t) * 0.5 +
                         np.sin(2 * np.pi * frequency * 2 * t) * 0.3 +
                         np.sin(2 * np.pi * frequency * 3 * t) * 0.2 +
                         np.sin(2 * np.pi * frequency * 5 * t) * 0.1)

                # Slow attack dla strings
                attack = int(0.2 * sample_rate)
                envelope = np.ones_like(audio)
                if len(envelope) > attack:
                    envelope[:attack] = np.linspace(0, 1, attack)

                audio *= envelope

            elif instrument == "pad":
                # Pad - very soft, multiple frequencies
                frequencies = [frequency, frequency * 1.25, frequency * 1.5, frequency * 2.0]
                audio = np.zeros_like(t)
                for i, freq in enumerate(frequencies):
                    audio += np.sin(2 * np.pi * freq * t) * (0.4 / (i + 1))

                # Very slow attack
                attack = int(0.5 * sample_rate)
                envelope = np.ones_like(audio)
                if len(envelope) > attack:
                    envelope[:attack] = np.linspace(0, 1, attack)

                audio *= envelope

            else:
                # Default sine wave
                audio = np.sin(2 * np.pi * frequency * t)

            # Apply velocity
            audio = audio * amplitude

        return audio

    def _mix_tracks(self, audio_tracks: List[np.ndarray]) -> np.ndarray:
        """Miksal ścieżki audio w jeden sygnał stereo"""
        if not audio_tracks:
            return np.zeros((1000, 2))  # Empty stereo audio

        # Znajdź najdłuższą ścieżkę
        max_length = max(len(track) for track in audio_tracks)

        # Utwórz stereo mix
        mixed_audio = np.zeros((max_length, 2))

        for i, track in enumerate(audio_tracks):
            # Pad shorter tracks with zeros
            if len(track) < max_length:
                padded_track = np.pad(track, (0, max_length - len(track)))
            else:
                padded_track = track

            # Simple stereo panning - alternate left/right for different tracks
            if i % 2 == 0:
                # Left channel bias
                mixed_audio[:, 0] += padded_track * 0.7
                mixed_audio[:, 1] += padded_track * 0.3
            else:
                # Right channel bias
                mixed_audio[:, 0] += padded_track * 0.3
                mixed_audio[:, 1] += padded_track * 0.7

        # Normalize to prevent clipping
        max_amplitude = np.max(np.abs(mixed_audio))
        if max_amplitude > 0:
            mixed_audio = mixed_audio / max_amplitude * 0.9

        return mixed_audio

    def _save_audio(self, audio_data: np.ndarray, output_path: str):
        """Zapisuje audio do pliku WAV"""
        try:
            from scipy.io.wavfile import write

            # Konwertuj do int16
            if audio_data.dtype != np.int16:
                audio_int16 = (audio_data * 32767).astype(np.int16)
            else:
                audio_int16 = audio_data

            write(output_path, self.settings.sample_rate, audio_int16)

        except ImportError:
            print("⚠️  scipy not available, saving as text file")
            np.savetxt(output_path.replace('.wav', '.txt'), audio_data)


class AudioProcessor:
    """Klasa do post-processingu audio (efekty, mastering)"""

    def __init__(self):
        pass

    def add_reverb(self, audio: np.ndarray, room_size: float = 0.5, damping: float = 0.5) -> np.ndarray:
        """Dodaje pogłos do audio"""
        # Sprawdź czy audio nie jest za duże
        if len(audio.shape) > 1 and audio.shape[1] > 2:
            audio = audio[:, 0]

        if len(audio) > 44100 * 10:
            audio = audio[:44100 * 10]
            print("Warning: Audio truncated to 10 seconds")

        # Prosty algorytm reverb
        delay_samples = [
            int(0.030 * 44100),  # 30ms
            int(0.047 * 44100),  # 47ms
        ]

        reverb_audio = audio.copy()

        for delay in delay_samples:
            if delay < len(audio):
                delayed = np.pad(audio[:-delay], (delay, 0), mode='constant')
                if len(delayed) == len(reverb_audio):
                    reverb_audio += delayed * (room_size * 0.3)

        return audio * (1 - room_size * 0.5) + reverb_audio * (room_size * 0.5)

    def add_compression(self, audio: np.ndarray, threshold: float = 0.7, ratio: float = 4.0) -> np.ndarray:
        """Dodaje kompresję do audio"""
        compressed = audio.copy()

        # Simple threshold compression
        over_threshold = np.abs(compressed) > threshold
        compressed[over_threshold] = np.sign(compressed[over_threshold]) * (
                threshold + (np.abs(compressed[over_threshold]) - threshold) / ratio
        )

        return compressed


def test_midi_to_audio():
    """Test konwersji MIDI na audio"""
    print("🎵 Testing MIDI to Audio synthesis...")

    # Najpierw generujemy MIDI
    from midi_generator import test_basic_generation
    midi_file = test_basic_generation()

    # Utwórz syntezator
    synthesizer = SimpleSynthesizer()

    # Załaduj sample dla instrumentów
    synthesizer.load_samples_for_instruments(["piano", "strings", "pad"], "ambient")

    # Konwertuj MIDI na audio
    midi_path = "output/midi/test_ambient_peaceful.mid"
    audio_path = "output/audio/test_ambient_peaceful.wav"

    # Upewnij się, że katalog audio istnieje
    os.makedirs("app/tests/output/audio", exist_ok=True)

    synthesizer.synthesize_midi_to_audio(midi_path, audio_path)

    # Test post-processingu
    print("🎛️  Testing audio post-processing...")
    processor = AudioProcessor()

    # Załaduj wygenerowane audio i dodaj efekty
    # try:
    #     from scipy.io.wavfile import read, write
    #     sample_rate, audio_data = read(audio_path)
    #
    #     # Dodaj reverb
    #     reverb_audio = processor.add_reverb(audio_data.astype(np.float32) / 32768.0, room_size=0.3)
    #
    #     # Dodaj kompresję
    #     final_audio = processor.add_compression(reverb_audio, threshold=0.8, ratio=3.0)
    #
    #     # Zapisz processed version
    #     processed_path = audio_path.replace('.wav', '_processed.wav')
    #     write(processed_path, sample_rate, (final_audio * 32767).astype(np.int16))
    #     print(f"  ✅ Processed audio saved: {processed_path}")
    #
    # except ImportError:
    #     print("  ⚠️  scipy not available, skipping post-processing")

    print("✅ MIDI to Audio synthesis test completed!")


if __name__ == "__main__":
    test_midi_to_audio()