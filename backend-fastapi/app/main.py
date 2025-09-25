from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database.connection import Base, engine
from .auth.router import router as auth_router
from .users import router as users_router
from .database.seeder import seed_users
from fastapi.staticfiles import StaticFiles
try:
    from .tests.parametrize_advanced_test.router import router as param_adv_router
    _PARAM_ADV_AVAILABLE = True
except Exception as e:  # broad for diagnostic
    param_adv_router = None  # type: ignore
    _PARAM_ADV_AVAILABLE = False
    _PARAM_ADV_IMPORT_ERROR = str(e)
try:
    from .tests.parametrize_sampling_test.router import router as param_sampling_router
    _PARAM_SAMPLING_AVAILABLE = True
except Exception as e:  # broad for diagnostic
    param_sampling_router = None  # type: ignore
    _PARAM_SAMPLING_AVAILABLE = False
    _PARAM_SAMPLING_IMPORT_ERROR = str(e)
import subprocess
import sys
from pathlib import Path

import os
os.environ["PYTHONIOENCODING"] = "utf-8"

# Load .env early so downstream modules (sample fetcher) see FREESOUND_API_KEY
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass


app = FastAPI(
    title="AIR 4.0 API",
    description="API for music generation platform",
    version="1.0.0"
)

# Konfiguracja CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Upewnij się, że tabele są utworzone
Base.metadata.create_all(bind=engine)

# Wywołaj seeder przy starcie aplikacji
seed_users()

# Dodaj routery
app.include_router(auth_router, prefix="/api")
app.include_router(users_router, prefix="/api")
if _PARAM_ADV_AVAILABLE and param_adv_router:
    app.include_router(param_adv_router, prefix="/api")
    # Serve generated artifacts (MIDI/images) for param-adv module
    try:
        param_adv_output = Path(__file__).parent / "tests" / "parametrize_advanced_test" / "output"
        param_adv_output.mkdir(parents=True, exist_ok=True)
        app.mount("/api/param-adv/output", StaticFiles(directory=str(param_adv_output)), name="param_adv_output")
    except Exception as e:
        print("[WARN] failed to mount param-adv static output:", e)
    # Debug: list param-adv routes to verify availability
    try:
        param_routes = [getattr(r, "path", str(r)) for r in app.routes if "/param-adv" in getattr(r, "path", "")]
        print("[param-adv] registered routes:")
        for p in sorted(param_routes):
            print("   ", p)
    except Exception as e:
        print("[WARN] failed to enumerate param-adv routes:", e)
else:
    print("[WARN] param_adv_router not loaded:", globals().get('_PARAM_ADV_IMPORT_ERROR'))

# Include new local-sample parametrized router
if _PARAM_SAMPLING_AVAILABLE and param_sampling_router:
    app.include_router(param_sampling_router, prefix="/api")
    try:
        param_sampling_output = Path(__file__).parent / "tests" / "parametrize_sampling_test" / "output"
        param_sampling_output.mkdir(parents=True, exist_ok=True)
        app.mount("/api/param-sampling/output", StaticFiles(directory=str(param_sampling_output)), name="param_sampling_output")
    except Exception as e:
        print("[WARN] failed to mount param-sampling static output:", e)
    try:
        sampling_routes = [getattr(r, "path", str(r)) for r in app.routes if "/param-sampling" in getattr(r, "path", "")]
        print("[param-sampling] registered routes:")
        for p in sorted(sampling_routes):
            print("   ", p)
    except Exception as e:
        print("[WARN] failed to enumerate param-sampling routes:", e)
else:
    print("[WARN] param_sampling_router not loaded:", globals().get('_PARAM_SAMPLING_IMPORT_ERROR'))


# MUSIC TEST ENDPOINTS - dodane bezpośrednio
def run_test_script(script_name: str):
    """Uruchamia skrypt testowy"""
    try:
        tests_dir = Path(__file__).parent / "tests" / "simple-sample-test"
        script_path = tests_dir / script_name

        if not script_path.exists():
            return {"success": False, "error": f"Skrypt {script_name} nie istnieje"}

        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(tests_dir),
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
        return {"success": False, "output": "", "error": "Timeout (30s)", "script": script_name}
    except Exception as e:
        return {"success": False, "output": "", "error": str(e), "script": script_name}


@app.post("/api/music-tests/run-midi")
def run_midi_test():
    return run_test_script("midi_generator.py")


@app.post("/api/music-tests/run-samples")
def run_samples_test():
    return run_test_script("sample_fetcher.py")


@app.post("/api/music-tests/run-audio")
def run_audio_test():
    return run_test_script("audio_synthesizer.py")


@app.post("/api/music-tests/run-full")
def run_full_test():
    return run_test_script("test_basic_generation.py")


@app.get("/api/music-tests/list-files")
def list_files():
    files = {"midi": [], "audio": [], "samples": []}
    tests_dir = Path(__file__).parent / "tests" / "simple-sample-test"
    output_dir = tests_dir / "output"

    if output_dir.exists():
        for file_type in ["midi", "audio", "samples"]:
            type_dir = output_dir / file_type
            if type_dir.exists():
                files[file_type] = [f.name for f in type_dir.glob("*") if f.is_file()]

    return files


@app.get("/")
def read_root():
    return {
        "message": "AIR 4.0 API is running",
        "version": "1.0.0",
        "features": {
            "auth": True,
            "users": True,
            "music_tests": True
        }
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/api/debug/routes")
def debug_routes():
    return {
        "param_adv_loaded": _PARAM_ADV_AVAILABLE,
        "param_adv_import_error": None if _PARAM_ADV_AVAILABLE else globals().get('_PARAM_ADV_IMPORT_ERROR'),
        "routes": [r.path for r in app.routes]
    }


@app.get("/api/param-adv/_routes")
def debug_param_adv_routes():
    try:
        param_routes = [getattr(r, "path", str(r)) for r in app.routes if "/param-adv" in getattr(r, "path", "")]
        return {"routes": sorted(param_routes)}
    except Exception as e:
        return {"error": str(e)}