import os, sys
from pathlib import Path

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
MIDI_DIR = OUTPUT_DIR / "midi"
AUDIO_DIR = OUTPUT_DIR / "audio"
SAMPLES_DIR = OUTPUT_DIR / "samples"

for d in (MIDI_DIR, AUDIO_DIR, SAMPLES_DIR):
    d.mkdir(parents=True, exist_ok=True)

sys.path.append(str(BASE_DIR))

from . import midi_generator, sample_fetcher, audio_synthesizer  # type: ignore

def main():
    print("🚀 Simple Sample Test Suite")
    print("Output directory:", OUTPUT_DIR)
    # Minimal example using existing midi_generator
    params = midi_generator.MusicParameters()
    gen = midi_generator.MidiGenerator(params)
    gen.generate_basic_track()
    gen.save_midi("quick_test.mid")
    print("✅ Generated quick_test.mid")

if __name__ == "__main__":
    main()