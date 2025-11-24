from fastapi import FastAPI
# hot-reload touch: inventory integration verified
from fastapi.middleware.cors import CORSMiddleware
from .database.connection import Base, engine
from .auth.router import router as auth_router
from .users import router as users_router
from .database.seeder import seed_users
from fastapi.staticfiles import StaticFiles
from pathlib import Path
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
try:
    from .tests.ai_param_test.router import router as ai_param_router  # type: ignore
    _AI_PARAM_AVAILABLE = True
except Exception as e:  # broad for diagnostic
    # Fallback: load from hyphenated folder 'ai-param-test' with a synthetic package so relative imports work
    ai_param_router = None  # type: ignore
    _AI_PARAM_AVAILABLE = False
    _AI_PARAM_IMPORT_ERROR = str(e)
    try:
        import importlib.util, types
        pkg_name = "app.tests.ai_param_test"
        spec_name = pkg_name + ".router"
        dir_path = Path(__file__).parent / "tests" / "ai-param-test"
        file_path = dir_path / "router.py"
        if file_path.exists():
            # Create a synthetic package module to back relative imports like `.parameters`
            if pkg_name not in sys.modules:
                pkg = types.ModuleType(pkg_name)
                pkg.__path__ = [str(dir_path)]  # type: ignore[attr-defined]
                sys.modules[pkg_name] = pkg
            spec = importlib.util.spec_from_file_location(spec_name, str(file_path))
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[spec_name] = module
                spec.loader.exec_module(module)  # type: ignore[attr-defined]
                ai_param_router = getattr(module, "router", None)  # type: ignore
                _AI_PARAM_AVAILABLE = ai_param_router is not None
                if not _AI_PARAM_AVAILABLE:
                    _AI_PARAM_IMPORT_ERROR = "router object not found in ai-param-test/router.py"
            else:
                _AI_PARAM_IMPORT_ERROR = "failed to create import spec for ai-param-test/router.py"
        else:
            _AI_PARAM_IMPORT_ERROR = f"not found: {file_path}"
    except Exception as e2:
        _AI_PARAM_IMPORT_ERROR = f"{_AI_PARAM_IMPORT_ERROR}; fallback failed: {e2}"
import subprocess
import sys
from pathlib import Path

import os
os.environ["PYTHONIOENCODING"] = "utf-8"

# Load .env early so downstream modules (sample fetcher / chat) see secrets
try:
    import os as _os
    from dotenv import load_dotenv, dotenv_values  # type: ignore
    env_file = Path(__file__).parent.parent / ".env"  # backend-fastapi/.env
    if env_file.exists():
        # Parse values explicitly and inject if missing/empty
        vals = dotenv_values(str(env_file))
        for k, v in vals.items():
            if v is None:
                continue
            if not _os.getenv(k):
                _os.environ[k] = v
        # Also call load_dotenv to ensure any other behavior (e.g., export) is preserved
        load_dotenv(dotenv_path=env_file, override=False)
    else:
        load_dotenv()
except Exception:
    pass

# Include AI render test router (1:1 copy of ai-param-test under new prefix) - define before router wiring
try:
    from .tests.ai_render_test.router import router as ai_render_router  # type: ignore
    _AI_RENDER_AVAILABLE = True
except Exception as e:  # broad for diagnostic
    # Fallback: load from hyphenated folder 'ai-render-test' with a synthetic package so relative imports work
    ai_render_router = None  # type: ignore
    _AI_RENDER_AVAILABLE = False
    _AI_RENDER_IMPORT_ERROR = str(e)
    try:
        import importlib.util, types
        pkg_name = "app.tests.ai_render_test"
        spec_name = pkg_name + ".router"
        dir_path = Path(__file__).parent / "tests" / "ai-render-test"
        file_path = dir_path / "router.py"
        if file_path.exists():
            # Create a synthetic package module to back relative imports like `.parameters`
            if pkg_name not in sys.modules:
                pkg = types.ModuleType(pkg_name)
                pkg.__path__ = [str(dir_path)]  # type: ignore[attr-defined]
                sys.modules[pkg_name] = pkg
            spec = importlib.util.spec_from_file_location(spec_name, str(file_path))
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[spec_name] = module
                spec.loader.exec_module(module)  # type: ignore[attr-defined]
                ai_render_router = getattr(module, "router", None)  # type: ignore
                _AI_RENDER_AVAILABLE = ai_render_router is not None
                if not _AI_RENDER_AVAILABLE:
                    _AI_RENDER_IMPORT_ERROR = "router object not found in ai-render-test/router.py"
            else:
                _AI_RENDER_IMPORT_ERROR = "failed to create import spec for ai-render-test/router.py"
        else:
            _AI_RENDER_IMPORT_ERROR = f"not found: {file_path}"
    except Exception as e2:
        _AI_RENDER_IMPORT_ERROR = f"{_AI_RENDER_IMPORT_ERROR}; fallback failed: {e2}"

# Include production param-generation module (separate step: AI MIDI plan)
try:
    from .air.param_generation.router import router as param_generation_router  # type: ignore
    _PARAM_GEN_AVAILABLE = True
except Exception as e:
    param_generation_router = None  # type: ignore
    _PARAM_GEN_AVAILABLE = False
    _PARAM_GEN_IMPORT_ERROR = str(e)
try:
    from .air.inventory.router import router as air_inventory_router  # type: ignore
    _AIR_INV_AVAILABLE = True
except Exception as e:
    air_inventory_router = None  # type: ignore
    _AIR_INV_AVAILABLE = False
    _AIR_INV_IMPORT_ERROR = str(e)
try:
    from .air.midi_generation.router import router as midi_generation_router  # type: ignore
    _MIDI_GEN_AVAILABLE = True
except Exception as e:
    midi_generation_router = None  # type: ignore
    _MIDI_GEN_AVAILABLE = False
    _MIDI_GEN_IMPORT_ERROR = str(e)


app = FastAPI(
    title="AIR 4.0 API",
    description="API for music generation platform",
    version="1.0.0"
)

# Konfiguracja CORS
app.add_middleware(
    CORSMiddleware,
    # Keep explicit common dev origins and add a regex for any localhost/127.0.0.1 port
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=86400,  # cache preflight for a day in dev
)

# Mount local_samples for sample previews (global, independent of ai-render-test)
try:
    repo_root = Path(__file__).resolve().parents[2]
    local_samples_dir = repo_root / "local_samples"
    if local_samples_dir.exists():
        app.mount("/api/local-samples", StaticFiles(directory=str(local_samples_dir)), name="local_samples")
    else:
        print("[WARN] local_samples directory not found:", local_samples_dir)
except Exception as e:
    print("[WARN] failed to mount local_samples:", e)

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

# Include AI param test router (next-gen variant)
if _AI_PARAM_AVAILABLE and ai_param_router:
    app.include_router(ai_param_router, prefix="/api")
    try:
        ai_param_output = Path(__file__).parent / "tests" / "ai-param-test" / "output"
        ai_param_output.mkdir(parents=True, exist_ok=True)
        app.mount("/api/ai-param-test/output", StaticFiles(directory=str(ai_param_output)), name="ai_param_output")
    except Exception as e:
        print("[WARN] failed to mount ai-param-test static output:", e)
    try:
        ai_routes = [getattr(r, "path", str(r)) for r in app.routes if "/ai-param-test" in getattr(r, "path", "")]
        print("[ai-param-test] registered routes:")
        for p in sorted(ai_routes):
            print("   ", p)
    except Exception as e:
        print("[WARN] failed to enumerate ai-param-test routes:", e)
else:
    print("[WARN] ai_param_router not loaded:", globals().get('_AI_PARAM_IMPORT_ERROR'))

# Include AI render test router
if _AI_RENDER_AVAILABLE and ai_render_router:
    app.include_router(ai_render_router, prefix="/api")
    try:
        ai_render_output = Path(__file__).parent / "tests" / "ai-render-test" / "output"
        ai_render_output.mkdir(parents=True, exist_ok=True)
        app.mount("/api/ai-render-test/output", StaticFiles(directory=str(ai_render_output)), name="ai_render_output")
    except Exception as e:
        print("[WARN] failed to mount ai-render-test static output:", e)
    try:
        ar_routes = [getattr(r, "path", str(r)) for r in app.routes if "/ai-render-test" in getattr(r, "path", "")]
        print("[ai-render-test] registered routes:")
        for p in sorted(ar_routes):
            print("   ", p)
    except Exception as e:
        print("[WARN] failed to enumerate ai-render-test routes:", e)
else:
    print("[WARN] ai_render_router not loaded:", globals().get('_AI_RENDER_IMPORT_ERROR'))

# (end of ai-render-test import definition)

# Mount param-generation router and its static outputs
if _PARAM_GEN_AVAILABLE and param_generation_router:
    app.include_router(param_generation_router, prefix="/api")
    try:
        param_gen_output = Path(__file__).parent / "air" / "param_generation" / "output"
        param_gen_output.mkdir(parents=True, exist_ok=True)
        app.mount("/api/param-generation/output", StaticFiles(directory=str(param_gen_output)), name="param_generation_output")
    except Exception as e:
        print("[WARN] failed to mount param-generation static output:", e)
    try:
        pg_routes = [getattr(r, "path", str(r)) for r in app.routes if "/param-generation" in getattr(r, "path", "")]
        print("[param-generation] registered routes:")
        for p in sorted(pg_routes):
            print("   ", p)
    except Exception as e:
        print("[WARN] failed to enumerate param-generation routes:", e)
else:
    print("[WARN] param_generation_router not loaded:", globals().get('_PARAM_GEN_IMPORT_ERROR'))

# Mount inventory router (sample catalog)
if _AIR_INV_AVAILABLE and air_inventory_router:
    app.include_router(air_inventory_router, prefix="/api")
    try:
        inv_routes = [getattr(r, "path", str(r)) for r in app.routes if "/air/inventory" in getattr(r, "path", "")]
        print("[air-inventory] registered routes:")
        for p in sorted(inv_routes):
            print("   ", p)
    except Exception as e:
        print("[WARN] failed to enumerate air-inventory routes:", e)
else:
    print("[WARN] air_inventory_router not loaded:", globals().get('_AIR_INV_IMPORT_ERROR'))

# Mount midi-generation router and its static outputs
if _MIDI_GEN_AVAILABLE and midi_generation_router:
    app.include_router(midi_generation_router, prefix="/api")
    try:
        midi_gen_output = Path(__file__).parent / "air" / "midi_generation" / "output"
        midi_gen_output.mkdir(parents=True, exist_ok=True)
        app.mount("/api/midi-generation/output", StaticFiles(directory=str(midi_gen_output)), name="midi_generation_output")
    except Exception as e:
        print("[WARN] failed to mount midi-generation static output:", e)
    try:
        mg_routes = [getattr(r, "path", str(r)) for r in app.routes if "/midi-generation" in getattr(r, "path", "")]
        print("[midi-generation] registered routes:")
        for p in sorted(mg_routes):
            print("   ", p)
    except Exception as e:
        print("[WARN] failed to enumerate midi-generation routes:", e)
else:
    print("[WARN] midi_generation_router not loaded:", globals().get('_MIDI_GEN_IMPORT_ERROR'))


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