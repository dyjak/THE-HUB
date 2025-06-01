
"""
Test podstawowego generowania muzyki zgodnie z dokumentacją AIR 4.0
"""

import os
import sys
from pathlib import Path

# Dodaj ścieżkę do modułu app
sys.path.append(str(Path(__file__).parent.parent))

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')



import midi_generator
import sample_fetcher
import audio_synthesizer


def create_output_directories():
    """Tworzy katalogi wyjściowe"""
    directories = [
        "app/tests/output",
        "app/tests/output/midi",
        "app/tests/output/audio",
        "app/tests/output/samples"
    ]

    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"📁 Created directory: {directory}")


def test_full_pipeline():
    """Test pełnego pipeline'u generowania muzyki"""
    print("🚀 Starting AIR 4.0 Music Generation Test")
    print("=" * 50)

    # 1. Utwórz katalogi
    create_output_directories()

    # 2. Test różnych gatunków i nastrojów
    test_cases = [
        {
            "name": "Ambient Peaceful",
            "params": midi_generator.MusicParameters(
                genre="ambient",
                mood="peaceful",
                tempo=60,
                key="F",
                instruments=["piano", "strings", "pad"]
            )
        },
        {
            "name": "Jazz Energetic",
            "params": midi_generator.MusicParameters(
                genre="jazz",
                mood="energetic",
                tempo=120,
                key="C",
                instruments=["piano", "bass"]
            )
        },
        {
            "name": "Rock Aggressive",
            "params": midi_generator.MusicParameters(
                genre="rock",
                mood="aggressive",
                tempo=140,
                key="G",
                instruments=["guitar", "bass", "drums"]
            )
        }
    ]

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n🎵 Test Case {i}: {test_case['name']}")
        print("-" * 30)

        # Generuj MIDI
        generator = midi_generator.MidiGenerator(test_case["params"])
        midi_file = generator.generate_basic_track()

        filename = f"test_{test_case['name'].lower().replace(' ', '_')}"
        midi_path = f"app/tests/output/midi/{filename}.mid"
        generator.save_midi(f"{filename}.mid")

        print(f"  ✅ MIDI generated: {midi_path}")

        # Wyświetl parametry
        params = test_case["params"]
        print(f"  📋 Parameters:")
        print(f"     Genre: {params.genre}")
        print(f"     Mood: {params.mood}")
        print(f"     Tempo: {params.tempo} BPM")
        print(f"     Key: {params.key}")
        print(f"     Instruments: {', '.join(params.instruments)}")


def test_parameter_interpretation():
    """Test interpretacji parametrów tekstowych na muzyczne"""
    print("\n🧠 Testing Parameter Interpretation")
    print("-" * 40)

    # Przykłady opisów tekstowych z dokumentacji
    text_descriptions = [
        "Stwórz spokojny podkład w stylu ambient z głębokim pogłosem",
        "Wygeneruj energetyczny utwór jazzowy o umiarkowanym tempie",
        "Zrób melancholijną melodię na pianino w tonacji A-moll"
    ]

    for desc in text_descriptions:
        print(f"\n📝 Description: '{desc}'")

        # Prosta interpretacja (w przyszłości z GPT)
        interpreted_params = interpret_text_to_parameters(desc)

        print(f"  🎼 Interpreted parameters:")
        for key, value in interpreted_params.items():
            print(f"     {key}: {value}")


def interpret_text_to_parameters(description: str) -> dict:
    """Prosta interpretacja tekstu na parametry muzyczne (prototype)"""
    params = {
        "genre": "ambient",
        "mood": "peaceful",
        "tempo": 80,
        "key": "C",
        "instruments": ["piano"]
    }

    # Proste słowa kluczowe
    if "ambient" in description.lower():
        params["genre"] = "ambient"
        params["instruments"] = ["piano", "strings", "pad"]
    elif "jazz" in description.lower():
        params["genre"] = "jazz"
        params["instruments"] = ["piano", "bass", "drums"]
    elif "rock" in description.lower():
        params["genre"] = "rock"
        params["instruments"] = ["guitar", "bass", "drums"]

    if "spokojny" in description.lower() or "peaceful" in description.lower():
        params["mood"] = "peaceful"
        params["tempo"] = 60
    elif "energet" in description.lower():
        params["mood"] = "energetic"
        params["tempo"] = 120
    elif "melanchol" in description.lower():
        params["mood"] = "melancholy"
        params["tempo"] = 70

    if "pianino" in description.lower() or "piano" in description.lower():
        params["instruments"] = ["piano"]

    if "a-moll" in description.lower():
        params["key"] = "Am"
    elif "f-dur" in description.lower():
        params["key"] = "F"

    return params


def check_requirements():
    """Sprawdza czy wymagane biblioteki są zainstalowane"""
    print("🔍 Checking requirements...")

    required_packages = [
        ("mido", "MIDI manipulation"),
        ("numpy", "Numerical operations"),
        ("scipy", "Audio processing (optional)"),
        ("requests", "HTTP requests")
    ]

    missing_packages = []

    for package, description in required_packages:
        try:
            __import__(package)
            print(f"  ✅ {package} - {description}")
        except ImportError:
            print(f"  ❌ {package} - {description} (MISSING)")
            missing_packages.append(package)

    if missing_packages:
        print(f"\n⚠️  Missing packages: {', '.join(missing_packages)}")
        print("   Install with: pip install " + " ".join(missing_packages))
        return False

    return True


def main():
    """Główna funkcja testowa"""
    print("🎼 AIR 4.0 - Music Generation Test Suite")
    print("=" * 50)

    # Sprawdź requirements
    if not check_requirements():
        print("❌ Requirements not met. Please install missing packages.")
        return

    try:
        # Test 1: Podstawowe generowanie MIDI
        print("\n📝 Test 1: Basic MIDI Generation")
        midi_generator.test_basic_generation()

        # Test 2: Pobieranie sampli
        print("\n📝 Test 2: Sample Fetching")
        sample_fetcher.test_sample_fetching()

        # Test 3: Konwersja MIDI na audio
        print("\n📝 Test 3: MIDI to Audio Synthesis")
        audio_synthesizer.test_midi_to_audio()

        # Test 4: Pełny pipeline
        print("\n📝 Test 4: Full Pipeline")
        test_full_pipeline()

        # Test 5: Interpretacja parametrów
        print("\n📝 Test 5: Parameter Interpretation")
        test_parameter_interpretation()

        print("\n🎉 All tests completed successfully!")
        print("\n📁 Check output files in: app/tests/output/")

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()