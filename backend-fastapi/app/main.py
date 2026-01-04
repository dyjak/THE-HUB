"""główna aplikacja fastapi.

ten moduł:
- konfiguruje aplikację (`FastAPI`) i cors
- ładuje `.env` możliwie wcześnie, żeby downstream moduły widziały sekrety
- montuje statyczne katalogi (np. `local_samples/`, outputy kroków pipeline)
- rejestruje routery (auth/users oraz moduły `air/*` w trybie best-effort)

uwaga:
- część modułów `air/*` może nie być dostępna, jeśli brakuje zależności; wtedy router nie jest montowany,
  a informacja trafia na stdout przez `print()`
"""

from fastapi import FastAPI
# hot-reload touch: integracja inventory potwierdzona
from fastapi.middleware.cors import CORSMiddleware
from .database.connection import Base, engine
from .auth.router import router as auth_router
from .users import router as users_router
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import os
import sys

os.environ["PYTHONIOENCODING"] = "utf-8"

# ładujemy `.env` wcześnie, żeby downstream moduły (np. sample fetcher / chat) widziały sekrety
try:
    import os as _os
    from dotenv import load_dotenv, dotenv_values  # type: ignore
    env_file = Path(__file__).parent.parent / ".env"  # backend-fastapi/.env
    if env_file.exists():
        # parsujemy wartości jawnie i wstrzykujemy tylko brakujące
        vals = dotenv_values(str(env_file))
        for k, v in vals.items():
            if v is None:
                continue
            if not _os.getenv(k):
                _os.environ[k] = v
        # dodatkowo wołamy load_dotenv, żeby zachować jego zachowanie (np. export)
        load_dotenv(dotenv_path=env_file, override=False)
    else:
        load_dotenv()
except Exception:
    pass

# moduły `air/*` ładujemy best-effort (mogą zależeć od zewnętrznych bibliotek)
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

# konfiguracja cors
app.add_middleware(
    CORSMiddleware,
    # trzymamy jawne originy dev i regex dla dowolnego localhost/127.0.0.1 z portem
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

# montujemy `local_samples/` do odsłuchu sampli (globalnie, niezależnie od testów)
try:
    repo_root = Path(__file__).resolve().parents[2]
    local_samples_dir = repo_root / "local_samples"
    if local_samples_dir.exists():
        app.mount("/api/local-samples", StaticFiles(directory=str(local_samples_dir)), name="local_samples")
    else:
        print("[WARN] nie znaleziono katalogu local_samples:", local_samples_dir)
except Exception as e:
    print("[WARN] nie udało się zamontować local_samples:", e)

# upewnij się, że tabele są utworzone (bez automatycznego seedowania użytkowników)
Base.metadata.create_all(bind=engine)

# dodaj routery
app.include_router(auth_router, prefix="/api")
app.include_router(users_router, prefix="/api")
# montujemy router param-generation oraz jego statyczne outputy
if _PARAM_GEN_AVAILABLE and param_generation_router:
    app.include_router(param_generation_router, prefix="/api")
    try:
        param_gen_output = Path(__file__).parent / "air" / "param_generation" / "output"
        param_gen_output.mkdir(parents=True, exist_ok=True)
        app.mount("/api/param-generation/output", StaticFiles(directory=str(param_gen_output)), name="param_generation_output")
    except Exception as e:
        print("[WARN] nie udało się zamontować statycznego outputu param-generation:", e)
    try:
        pg_routes = [getattr(r, "path", str(r)) for r in app.routes if "/param-generation" in getattr(r, "path", "")]
        print("[param-generation] zarejestrowane trasy:")
        for p in sorted(pg_routes):
            print("   ", p)
    except Exception as e:
        print("[WARN] nie udało się wypisać tras param-generation:", e)
else:
    print("[WARN] nie załadowano param_generation_router:", globals().get('_PARAM_GEN_IMPORT_ERROR'))

# montujemy router inventory (katalog sampli)
if _AIR_INV_AVAILABLE and air_inventory_router:
    app.include_router(air_inventory_router, prefix="/api")
    try:
        inv_routes = [getattr(r, "path", str(r)) for r in app.routes if "/air/inventory" in getattr(r, "path", "")]
        print("[air-inventory] zarejestrowane trasy:")
        for p in sorted(inv_routes):
            print("   ", p)
    except Exception as e:
        print("[WARN] nie udało się wypisać tras air-inventory:", e)
else:
    print("[WARN] nie załadowano air_inventory_router:", globals().get('_AIR_INV_IMPORT_ERROR'))

# montujemy router midi-generation oraz jego statyczne outputy
if _MIDI_GEN_AVAILABLE and midi_generation_router:
    app.include_router(midi_generation_router, prefix="/api")
    try:
        midi_gen_output = Path(__file__).parent / "air" / "midi_generation" / "output"
        midi_gen_output.mkdir(parents=True, exist_ok=True)
        app.mount("/api/midi-generation/output", StaticFiles(directory=str(midi_gen_output)), name="midi_generation_output")
    except Exception as e:
        print("[WARN] nie udało się zamontować statycznego outputu midi-generation:", e)
    try:
        mg_routes = [getattr(r, "path", str(r)) for r in app.routes if "/midi-generation" in getattr(r, "path", "")]
        print("[midi-generation] zarejestrowane trasy:")
        for p in sorted(mg_routes):
            print("   ", p)
    except Exception as e:
        print("[WARN] nie udało się wypisać tras midi-generation:", e)
else:
    print("[WARN] nie załadowano midi_generation_router:", globals().get('_MIDI_GEN_IMPORT_ERROR'))

# montujemy router render (export audio)
if _RENDER_AVAILABLE and render_router:
    app.include_router(render_router, prefix="/api")
    try:
        render_output = Path(__file__).parent / "air" / "render" / "output"
        render_output.mkdir(parents=True, exist_ok=True)
        # wystawiamy pliki audio pod /api/audio/{run_id}/...
        app.mount("/api/audio", StaticFiles(directory=str(render_output)), name="air_audio_output")
    except Exception as e:
        print("[WARN] nie udało się zamontować statycznego outputu render:", e)
else:
    print("[WARN] nie załadowano render_router:", globals().get('_RENDER_IMPORT_ERROR'))

# montujemy router user-projects (lista projektów dla użytkownika)
if _USER_PROJECTS_AVAILABLE and user_projects_router:
    app.include_router(user_projects_router, prefix="/api")
    try:
        up_routes = [getattr(r, "path", str(r)) for r in app.routes if "/air/user-projects" in getattr(r, "path", "")]
        print("[air-user-projects] zarejestrowane trasy:")
        for p in sorted(up_routes):
            print("   ", p)
    except Exception as e:
        print("[WARN] nie udało się wypisać tras air-user-projects:", e)
else:
    print("[WARN] nie załadowano user_projects_router:", globals().get('_USER_PROJECTS_IMPORT_ERROR'))

# montujemy router export (manifest do pobrania wszystkich artefaktów projektu)
if _EXPORT_AVAILABLE and export_router:
    app.include_router(export_router, prefix="/api")
else:
    print("[WARN] nie załadowano export_router:", globals().get('_EXPORT_IMPORT_ERROR'))

# montujemy router gallery (portfolio / linki soundcloud)
if _GALLERY_AVAILABLE and gallery_router:
    app.include_router(gallery_router, prefix="/api")
else:
    print("[WARN] nie załadowano gallery_router:", globals().get('_GALLERY_IMPORT_ERROR'))


@app.get("/")
def read_root():
    """prosty endpoint statusowy (root)."""
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
    """lekki healthcheck."""
    return {"status": "healthy"}


@app.get("/api/debug/routes")
def debug_routes():
    """zwraca listę zarejestrowanych tras (endpoint diagnostyczny)."""
    # część flag może nie istnieć, jeśli dany moduł debug/testowy nie był importowany.
    # nie chcemy, żeby endpoint diagnostyczny wywalał 500 przez NameError.
    return {
        "param_adv_loaded": bool(globals().get("_PARAM_ADV_AVAILABLE", False)),
        "param_adv_import_error": None if globals().get("_PARAM_ADV_AVAILABLE", False) else globals().get("_PARAM_ADV_IMPORT_ERROR"),
        "routes": [r.path for r in app.routes]
    }


@app.get("/api/param-adv/_routes")
def debug_param_adv_routes():
    """wypisuje trasy `/param-adv` (endpoint diagnostyczny)."""
    try:
        param_routes = [getattr(r, "path", str(r)) for r in app.routes if "/param-adv" in getattr(r, "path", "")]
        return {"routes": sorted(param_routes)}
    except Exception as e:
        return {"error": str(e)}