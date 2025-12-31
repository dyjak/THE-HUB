from fastapi import FastAPI
# hot-reload touch: inventory integration verified
from fastapi.middleware.cors import CORSMiddleware
from .database.connection import Base, engine
from .auth.router import router as auth_router
from .users import router as users_router
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import os
import sys

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
try:
    from .air.render.router import router as render_router  # type: ignore
    _RENDER_AVAILABLE = True
except Exception as e:
    render_router = None  # type: ignore
    _RENDER_AVAILABLE = False
    _RENDER_IMPORT_ERROR = str(e)
try:
    from .air.user_projects_router import router as user_projects_router  # type: ignore
    _USER_PROJECTS_AVAILABLE = True
except Exception as e:
    user_projects_router = None  # type: ignore
    _USER_PROJECTS_AVAILABLE = False
    _USER_PROJECTS_IMPORT_ERROR = str(e)

try:
    from .air.export.router import router as export_router  # type: ignore
    _EXPORT_AVAILABLE = True
except Exception as e:
    export_router = None  # type: ignore
    _EXPORT_AVAILABLE = False
    _EXPORT_IMPORT_ERROR = str(e)

try:
    from .air.gallery.router import router as gallery_router  # type: ignore
    _GALLERY_AVAILABLE = True
except Exception as e:
    gallery_router = None  # type: ignore
    _GALLERY_AVAILABLE = False
    _GALLERY_IMPORT_ERROR = str(e)


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

# Upewnij się, że tabele są utworzone (bez automatycznego seedowania użytkowników)
Base.metadata.create_all(bind=engine)

# Dodaj routery
app.include_router(auth_router, prefix="/api")
app.include_router(users_router, prefix="/api")
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

# Mount render router (audio export)
if _RENDER_AVAILABLE and render_router:
    app.include_router(render_router, prefix="/api")
    try:
        render_output = Path(__file__).parent / "air" / "render" / "output"
        render_output.mkdir(parents=True, exist_ok=True)
        # Expose audio files under /api/audio/{run_id}/...
        app.mount("/api/audio", StaticFiles(directory=str(render_output)), name="air_audio_output")
    except Exception as e:
        print("[WARN] failed to mount render static output:", e)
else:
    print("[WARN] render_router not loaded:", globals().get('_RENDER_IMPORT_ERROR'))

# Mount user-projects router (simple listing for current user)
if _USER_PROJECTS_AVAILABLE and user_projects_router:
    app.include_router(user_projects_router, prefix="/api")
    try:
        up_routes = [getattr(r, "path", str(r)) for r in app.routes if "/air/user-projects" in getattr(r, "path", "")]
        print("[air-user-projects] registered routes:")
        for p in sorted(up_routes):
            print("   ", p)
    except Exception as e:
        print("[WARN] failed to enumerate air-user-projects routes:", e)
else:
    print("[WARN] user_projects_router not loaded:", globals().get('_USER_PROJECTS_IMPORT_ERROR'))

# Mount export router (manifest for downloading all project artifacts)
if _EXPORT_AVAILABLE and export_router:
    app.include_router(export_router, prefix="/api")
else:
    print("[WARN] export_router not loaded:", globals().get('_EXPORT_IMPORT_ERROR'))

# Mount gallery router (portfolio / SoundCloud embeds)
if _GALLERY_AVAILABLE and gallery_router:
    app.include_router(gallery_router, prefix="/api")
else:
    print("[WARN] gallery_router not loaded:", globals().get('_GALLERY_IMPORT_ERROR'))


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