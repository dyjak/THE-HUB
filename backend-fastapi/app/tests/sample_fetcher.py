import sys

import requests
import json
import os
from typing import Dict, List, Optional
from dataclasses import dataclass
import tempfile
from urllib.parse import urljoin

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')


@dataclass
class SampleInfo:
    """Informacje o samplu"""
    id: str
    name: str
    url: str
    duration: float
    instrument: str
    key: Optional[str] = None
    bpm: Optional[int] = None


class SampleFetcher:
    """Klasa do pobierania sampli z różnych źródeł"""

    def __init__(self):
        # Możesz dodać API klucze do .env później
        self.freesound_api_key = None  # Będzie potrzebny dla Freesound API
        self.temp_dir = tempfile.gettempdir()

    def get_basic_samples(self) -> Dict[str, SampleInfo]:
        """Zwraca podstawowe sample wbudowane (prosthetic samples)"""
        # Na początek używamy prostych tonów generowanych programowo
        basic_samples = {
            "piano_c4": SampleInfo(
                id="piano_c4",
                name="Piano C4",
                url="generated://piano/c4",
                duration=2.0,
                instrument="piano",
                key="C"
            ),
            "strings_pad": SampleInfo(
                id="strings_pad",
                name="String Pad",
                url="generated://strings/pad",
                duration=4.0,
                instrument="strings"
            ),
            "ambient_pad": SampleInfo(
                id="ambient_pad",
                name="Ambient Pad",
                url="generated://pad/ambient",
                duration=8.0,
                instrument="pad"
            )
        }
        return basic_samples

    def search_freesound_samples(self, query: str, instrument: str = None) -> List[SampleInfo]:
        """Wyszukuje sample w Freesound.org"""
        if not self.freesound_api_key:
            print("⚠️  Freesound API key not configured, using basic samples")
            return list(self.get_basic_samples().values())

        # TODO: Implementacja Freesound API
        # Dokumentacja: https://freesound.org/docs/api/
        """
        url = "https://freesound.org/apiv2/search/text/"
        params = {
            "query": query,
            "filter": f"type:wav duration:[0.5 TO 10]",
            "fields": "id,name,previews,duration,analysis",
            "token": self.freesound_api_key
        }

        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            samples = []
            for result in data.get("results", []):
                sample = SampleInfo(
                    id=str(result["id"]),
                    name=result["name"],
                    url=result["previews"]["preview-hq-mp3"],
                    duration=result["duration"],
                    instrument=instrument or "unknown"
                )
                samples.append(sample)
            return samples
        """
        return []

    def get_samples_for_genre(self, genre: str) -> Dict[str, List[SampleInfo]]:
        """Zwraca odpowiednie sample dla gatunku muzycznego"""
        genre_mappings = {
            "ambient": {
                "instruments": ["pad", "strings", "piano"],
                "queries": ["ambient pad", "soft strings", "gentle piano"]
            },
            "jazz": {
                "instruments": ["piano", "bass", "drums", "saxophone"],
                "queries": ["jazz piano", "upright bass", "jazz drums", "smooth sax"]
            },
            "rock": {
                "instruments": ["guitar", "bass", "drums"],
                "queries": ["electric guitar", "rock bass", "rock drums"]
            },
            "techno": {
                "instruments": ["synth", "bass", "drums"],
                "queries": ["techno synth", "electronic bass", "electronic drums"]
            }
        }

        mapping = genre_mappings.get(genre, genre_mappings["ambient"])
        samples_by_instrument = {}

        # Na razie zwracamy podstawowe sample
        basic_samples = self.get_basic_samples()

        for instrument in mapping["instruments"]:
            instrument_samples = [
                sample for sample in basic_samples.values()
                if sample.instrument == instrument
            ]
            if instrument_samples:
                samples_by_instrument[instrument] = instrument_samples

        return samples_by_instrument

    def download_sample(self, sample: SampleInfo, output_dir: str = None) -> str:
        """Pobiera sample do lokalnego pliku"""
        if output_dir is None:
            output_dir = "output/samples"

        os.makedirs(output_dir, exist_ok=True)

        if sample.url.startswith("generated://"):
            # Dla wygenerowanych sampli, tworzymy placeholder
            file_path = os.path.join(output_dir, f"{sample.id}.wav")
            self._generate_placeholder_audio(sample, file_path)
            return file_path
        else:
            # Pobieranie prawdziwego pliku
            response = requests.get(sample.url, stream=True)
            if response.status_code == 200:
                file_path = os.path.join(output_dir, f"{sample.id}.wav")
                with open(file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                return file_path

        return None

    def _generate_placeholder_audio(self, sample: SampleInfo, file_path: str):
        """Generuje placeholder audio dla testów"""
        try:
            import numpy as np
            from scipy.io.wavfile import write

            sample_rate = 44100
            duration = sample.duration
            t = np.linspace(0, duration, int(sample_rate * duration))

            # Generuj prosty sygnał w zależności od instrumentu
            if sample.instrument == "piano":
                # Prosty ton C4 (261.63 Hz) z harmonicznymi
                frequency = 261.63
                audio = (np.sin(2 * np.pi * frequency * t) * 0.3 +
                         np.sin(2 * np.pi * frequency * 2 * t) * 0.1 +
                         np.sin(2 * np.pi * frequency * 3 * t) * 0.05)
                # Envelope ADSR
                attack = int(0.1 * sample_rate)
                release = int(0.5 * sample_rate)
                envelope = np.ones_like(audio)
                envelope[:attack] = np.linspace(0, 1, attack)
                envelope[-release:] = np.linspace(1, 0, release)
                audio *= envelope

            elif sample.instrument == "strings":
                # Akord (C-E-G)
                freq_c = 261.63
                freq_e = 329.63
                freq_g = 392.00
                audio = (np.sin(2 * np.pi * freq_c * t) * 0.3 +
                         np.sin(2 * np.pi * freq_e * t) * 0.3 +
                         np.sin(2 * np.pi * freq_g * t) * 0.3)

            elif sample.instrument == "pad":
                # Ambient pad z multiple freq
                frequencies = [261.63, 329.63, 392.00, 523.25]  # C4, E4, G4, C5
                audio = np.zeros_like(t)
                for freq in frequencies:
                    audio += np.sin(2 * np.pi * freq * t) * 0.2
                # Slow attack
                attack = int(1.0 * sample_rate)
                envelope = np.ones_like(audio)
                envelope[:attack] = np.linspace(0, 1, attack)
                audio *= envelope

            else:
                # Default sine wave
                audio = np.sin(2 * np.pi * 440 * t) * 0.3

            # Normalizuj i zapisz
            audio = np.clip(audio, -1, 1)
            write(file_path, sample_rate, (audio * 32767).astype(np.int16))
            print(f"File size: {os.path.getsize(file_path)} bytes")
            print(f"File exists: {os.path.exists(file_path)}")
            print(f"📄 Generated placeholder audio: {file_path}")

        except ImportError:
            print("⚠️  scipy not available, creating empty file")
            with open(file_path, 'w') as f:
                f.write("# Placeholder audio file")


def test_sample_fetching():
    """Test pobierania sampli"""
    fetcher = SampleFetcher()

    # Test podstawowych sampli
    print("🎵 Testing basic samples...")
    basic_samples = fetcher.get_basic_samples()
    for sample_id, sample in basic_samples.items():
        print(f"  - {sample.name} ({sample.instrument}, {sample.duration}s)")

    # Test sampli dla gatunku
    print("\n🎼 Testing genre-specific samples...")
    ambient_samples = fetcher.get_samples_for_genre("ambient")
    for instrument, samples in ambient_samples.items():
        print(f"  {instrument}: {len(samples)} samples")
        for sample in samples:
            file_path = fetcher.download_sample(sample)
            print(f"    ✅ Downloaded: {file_path}")

    print("\n✅ Sample fetching test completed!")


if __name__ == "__main__":
    test_sample_fetching()