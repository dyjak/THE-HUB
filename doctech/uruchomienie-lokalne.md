# Uruchomienie systemu lokalnie (Windows) — instrukcja

Ten rozdział opisuje, jak postawić projekt lokalnie mając repozytorium na dysku. Repo składa się z:

- backendu FastAPI: `backend-fastapi/`
- frontendu Next.js: `frontend-next/`
- lokalnej biblioteki sampli audio: `local_samples/`
- katalogów wynikowych/poprzednich exportów: `processed_projs/` (nie jest wymagane do startu)

Instrukcja zakłada Windows (repo ma skrypty `.bat`). Jeśli pracujesz na Linux/macOS, komendy są analogiczne, ale ścieżki/aktywacja venv będą inne.

---

## 0) Wymagania wstępne

Zainstaluj:

- Git
- Python 3.10+ (rekomendowane 3.11+)
- Node.js 18+ (rekomendowane 20+)
- (opcjonalnie, ale często potrzebne na Windows) **Microsoft Visual C++ Build Tools** — tylko jeśli `pip` nie ma gotowych wheel’i i próbuje kompilować np. `numpy/scipy`

Uwaga dot. audio:
- Render zakłada stały `sample_rate = 44100`. Najlepsze rezultaty będą, gdy sample (zwłaszcza `.wav`) są w 44.1 kHz.

---

## 1) Struktura repo (co jest czym)

Top-level:

- `start.bat` — uruchamia backend (`uvicorn`) i frontend (`npm run dev`) w osobnych oknach
- `test_render.bat` — uruchamia minimalny test renderu (CLI)
- `inventory-rebuild.bat` — pomocniczy (uwaga: druga komenda nie wykona się dopóki nie zakończysz uvicorn)
- `hard_reset.bat` — zawiera komendy PowerShell do ubicia procesów (mimo rozszerzenia `.bat`)

Backend:

- `backend-fastapi/app/main.py` — entrypoint FastAPI, ładowanie `.env`, CORS, DB `users.db`, montowanie routerów i katalogów statycznych
- `backend-fastapi/app/air/*` — pipeline AIR:
  - `param_generation` → plan parametrów (LLM)
  - `midi_generation` → JSON MIDI + artefakty (LLM)
  - `render` → render WAV ze sample (bez LLM)
  - `inventory` → katalog sampli (`inventory.json`)
  - `providers` → klienci i lista modeli providerów (OpenAI/Anthropic/Gemini/OpenRouter)

Frontend:

- `frontend-next/src/app/*` — Next.js App Router
- autoryzacja: NextAuth (Credentials Provider) loguje przez backend (`POST /api/login`)

---

## 2) Konfiguracja backendu (FastAPI)

### 2.1) Utworzenie virtualenv i instalacja zależności

W PowerShell/CMD w katalogu repo:

1) Wejdź do backendu:

```bat
cd backend-fastapi
```

2) Utwórz venv (w repo jest oczekiwany katalog `backend-fastapi/venv/`):

```bat
python -m venv venv
```

3) Aktywuj środowisko:

```bat
venv\Scripts\activate
```

4) Zainstaluj zależności:

```bat
pip install -r requirements.txt
```

### 2.2) Plik `.env` (opcjonalny, ale praktycznie wymagany do AI)

Backend próbuje wczytać `backend-fastapi/.env` bardzo wcześnie (zanim zaimportuje moduły providerów).

Utwórz plik `backend-fastapi/.env` jeśli chcesz używać kroków opartych o LLM (param/midi). Minimalnie zalecane:

```env
# JWT (ważne dla produkcji; lokalnie też warto ustawić)
AUTH_SECRET_KEY=change-this-in-local

# Co najmniej jeden provider AI (opcjonalnie)
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GOOGLE_API_KEY=
OPENROUTER_API_KEY=

# (opcjonalnie) wybór modeli
OPENAI_MODEL=gpt-4o-mini
ANTHROPIC_MODEL=claude-3-5-haiku-latest
GOOGLE_MODEL=gemini-3-pro-preview
OPENROUTER_MODEL=meta-llama/llama-3.1-8b-instruct:free
```

Uwaga:
- Backend wystartuje także bez tych zmiennych, ale funkcje AI mogą zwracać błędy konfiguracyjne.
- Wartości ustawione w systemowym ENV mają pierwszeństwo (plik `.env` ich nie nadpisuje).

### 2.3) Uruchomienie backendu

Zawsze uruchamiaj z katalogu `backend-fastapi/` (ważne dla SQLite `users.db`, bo jest względne do CWD).

```bat
uvicorn app.main:app --reload --port 8000
```

Szybkie endpointy diagnostyczne:

- `GET http://127.0.0.1:8000/health`
- `GET http://127.0.0.1:8000/api/debug/routes`

---

## 3) Konfiguracja frontendu (Next.js)

### 3.1) Instalacja zależności

W nowym terminalu z katalogu repo:

```bat
cd frontend-next
npm install
```

(Alternatywnie możesz użyć `pnpm`, ale w repo skrypt `start.bat` używa `npm run dev`.)

### 3.2) Zmienna `NEXT_PUBLIC_BACKEND_URL`

Jeśli backend działa na domyślnym adresie, nie musisz nic ustawiać. W przeciwnym razie utwórz `frontend-next/.env.local`:

```env
NEXT_PUBLIC_BACKEND_URL=http://127.0.0.1:8000
```

### 3.3) Start frontendu

```bat
npm run dev
```

Aplikacja: `http://localhost:3000`

---

## 4) Szybki start (skrypt)

Z katalogu głównego repo:

```bat
start.bat
```

Co robi skrypt:
- próbuje aktywować `backend-fastapi\\venv` (jeśli istnieje)
- uruchamia `uvicorn` z `--reload` w osobnym oknie
- uruchamia frontend `npm run dev` w osobnym oknie

Jeśli w backendzie nie masz venv w `backend-fastapi/venv`, skrypt wypisze ostrzeżenie — wtedy użyj instrukcji z sekcji 2.

---

## 5) Sample library i inventory

### 5.1) Skąd backend bierze sample

Repo zakłada katalog `local_samples/` w root. Backend montuje go statycznie:

- `/api/local-samples/<path>`

### 5.2) `inventory.json` (kanoniczny katalog)

`backend-fastapi/app/air/inventory/inventory.json` jest generowany automatycznie ze skanu `local_samples/`.

Jeśli `inventory.json` nie istnieje, backend potrafi go zbudować „w locie” przy pierwszym użyciu.

### 5.3) Wymuszenie przebudowy inventory

Najprościej przez HTTP (gdy backend już działa):

- szybki rebuild: `POST http://127.0.0.1:8000/api/air/inventory/rebuild`
- deep rebuild (wolniejszy, liczy RMS/FFT dla WAV): `POST http://127.0.0.1:8000/api/air/inventory/rebuild?mode=deep`

Alternatywnie z CLI (z aktywnym venv):

```bat
cd backend-fastapi
python -c "from app.air.inventory.inventory import build_inventory; build_inventory(deep=True)"
```

---

## 6) Logowanie i użytkownicy

Backend udostępnia:

- `POST /api/register` (username + 6-cyfrowy PIN)
- `POST /api/login` (zwraca JWT `access_token`)

Baza danych jest SQLite: `sqlite:///./users.db` → plik `users.db` tworzy się w bieżącym katalogu roboczym procesu.

---

## 7) Test renderu (smoke test)

Repo ma prosty test uruchamiany z root:

```bat
test_render.bat
```

To uruchamia:

- `python -m app.air.render.mini_pipeline_test`

Jeśli render działa, powinieneś zobaczyć tworzone pliki w `backend-fastapi/app/air/render/output/<run_id>/`.

---

## 8) Reset/ubijanie procesów (Windows)

Plik `hard_reset.bat` zawiera komendy PowerShell do ubicia procesów `uvicorn`, `python`, `node`.

Ponieważ to nie jest klasyczny batch, najbezpieczniej:
- otworzyć go i wkleić komendy do PowerShell, albo
- zmienić nazwę na `hard_reset.ps1` i uruchomić jako skrypt PowerShell.

---

## 9) Typowe problemy

- `pip install` wywala się na `numpy/scipy` → doinstaluj Microsoft C++ Build Tools lub zaktualizuj pip (`python -m pip install -U pip`) i spróbuj ponownie.
- Backend startuje, ale endpointy AI zwracają błąd → ustaw klucze w `backend-fastapi/.env`.
- „Zniknęli” użytkownicy / baza jest pusta → prawdopodobnie backend został uruchomiony z innego katalogu i utworzył nowy `users.db` w innym miejscu.
- Render brzmi „za szybko/za wolno” → sample WAV mają inny sample rate niż 44100.

---

## 10) Minimalny checklist (dla dokumentacji)

- [ ] `backend-fastapi/venv` utworzone i zależności zainstalowane
- [ ] `backend-fastapi/.env` uzupełnione (co najmniej `AUTH_SECRET_KEY`, oraz klucze AI jeśli używasz LLM)
- [ ] `local_samples/` istnieje i ma pliki audio
- [ ] backend działa na `http://127.0.0.1:8000`
- [ ] `frontend-next` ma zależności i działa na `http://localhost:3000`
