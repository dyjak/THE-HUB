from fastapi import APIRouter
import subprocess
import sys
import os
from pathlib import Path

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')


router = APIRouter(prefix="/music-tests", tags=["music-tests"])

# Ścieżka do katalogu tests
TESTS_DIR = Path(__file__).parent.parent / "tests"


def run_script(script_name: str):
    """Uruchamia skrypt testowy"""
    try:
        script_path = TESTS_DIR / script_name

        # Uruchom skrypt
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(TESTS_DIR),
            capture_output=True,
            text=True,
            timeout=30
        )

        return {
            "success": result.returncode == 0,
            "output": result.stdout,
            "error": result.stderr,
            "script": script_name
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "output": "",
            "error": "Script timeout (30s)",
            "script": script_name
        }
    except Exception as e:
        return {
            "success": False,
            "output": "",
            "error": str(e),
            "script": script_name
        }


@router.get("/")
def test_info():
    return {
        "available_tests": [
            "midi_generator.py",
            "sample_fetcher.py",
            "audio_synthesizer.py",
            "test_basic_generation.py"
        ]
    }


@router.post("/run-midi")
def run_midi_test():
    """Uruchom test generowania MIDI"""
    return run_script("midi_generator.py")


@router.post("/run-samples")
def run_samples_test():
    """Uruchom test sampli"""
    return run_script("sample_fetcher.py")


@router.post("/run-audio")
def run_audio_test():
    """Uruchom test syntezy audio"""
    return run_script("audio_synthesizer.py")


@router.post("/run-full")
def run_full_test():
    """Uruchom pełny test"""
    return run_script("test_basic_generation.py")


@router.get("/list-files")
def list_files():
    """Lista wygenerowanych plików"""
    files = {"midi": [], "audio": [], "samples": []}

    output_dir = TESTS_DIR / "output"
    if output_dir.exists():
        for file_type in ["midi", "audio", "samples"]:
            type_dir = output_dir / file_type
            if type_dir.exists():
                files[file_type] = [f.name for f in type_dir.glob("*") if f.is_file()]

    return files