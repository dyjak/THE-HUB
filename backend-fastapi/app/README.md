# `app/` - backend FastAPI (punkt wejścia: `main.py`)

Ten katalog to właściwa aplikacja backendu (FastAPI) dla repo.

Najważniejszy plik to `app/main.py`, który odpowiada za:

- wczesne ładowanie `.env`,
- konfigurację CORS,
- inicjalizację bazy danych (tworzenie tabel),
- montowanie routerów API,
- montowanie statycznych katalogów (sample i outputy pipeline).

## 1. Punkt wejścia: `app/main.py`

### 1.1. Wczesne ładowanie `.env`

`main.py` próbuje wczytać `backend-fastapi/.env` **zanim** zaimportuje moduły, które potrzebują kluczy API.

Zachowanie:

- jeśli `backend-fastapi/.env` istnieje: parsuje go przez `dotenv_values()` i ustawia tylko brakujące zmienne środowiskowe, a potem woła `load_dotenv(..., override=False)`,
- jeśli nie istnieje: robi `load_dotenv()` (domyślne zachowanie biblioteki).

Efekt: jeśli ustawisz zmienne w systemie/CI, `.env` ich nie nadpisze.

### 1.2. FastAPI + CORS

CORS jest ustawiony na środowisko developerskie:

- dozwolone originy: `http://localhost:3000`, `http://127.0.0.1:3000`, `http://localhost:5173`, `http://127.0.0.1:5173`
- plus regex na dowolny `localhost/127.0.0.1` z portem.

Uwaga: jest ustawione `allow_credentials=True`.

### 1.3. Baza danych: `Base.metadata.create_all()`

Przy starcie aplikacji `main.py` zawsze woła:

- `Base.metadata.create_all(bind=engine)`

To zapewnia, że tabele istnieją (bez automatycznego seedowania użytkowników).

Szczegóły DB są w [database/README.md](database/README.md).

### 1.4. Routery API (prefix `/api`)

`main.py` montuje routery z prefixem `/api`:

- auth: `POST /api/login`, `POST /api/register`
- users (admin/dev): `/api/users...`

Większość routerów AIR jest montowana „best-effort” (w `try/except`). Jeśli import się nie uda (np. brak zależności), backend nadal wstaje, a w konsoli pojawia się ostrzeżenie i dany feature jest po prostu niedostępny.

### 1.5. Statyczne mounty (pliki jako HTTP)

`main.py` montuje kilka katalogów jako statyczne zasoby:

- `local_samples/` (z repo) → `GET /api/local-samples/<path>`
- `app/air/param_generation/output` → `GET /api/param-generation/output/<path>`
- `app/air/midi_generation/output` → `GET /api/midi-generation/output/<path>`
- `app/air/render/output` → `GET /api/audio/<path>`

To jest kluczowe dla UX: API zwraca metadane/ścieżki, a frontend pobiera realne pliki (WAV/MID/SVG/JSON) po HTTP.

### 1.6. Endpointy diagnostyczne

`main.py` wystawia:

- `GET /` — prosty status + `features`
- `GET /health` — healthcheck
- `GET /api/debug/routes` — lista wszystkich `app.routes`
- `GET /api/param-adv/_routes` — debug dla `/param-adv` (jeśli ten moduł istnieje)

## 2. Struktura katalogu `app/`

- `air/` — pipeline generacji muzyki (szczegóły w [air/readme.md](air/readme.md))
- `auth/` — auth (PIN + JWT) (szczegóły w [auth/README.md](auth/README.md))
- `database/` — SQLAlchemy + narzędzia DB (szczegóły w [database/README.md](database/README.md))
- `users.py` + `users.md` — proste endpointy admin/dev dla użytkowników
- `tests/` — skrypty/testy developerskie

## 3. Uruchomienie lokalne (typowo)

Zwykle uruchamiasz z katalogu `backend-fastapi/`, np.:

- `uvicorn app.main:app --reload --port 8000`

Uwaga: SQLite `sqlite:///./users.db` zależy od bieżącego katalogu roboczego (CWD), więc uruchamianie z innego folderu może utworzyć nową bazę w innym miejscu.
