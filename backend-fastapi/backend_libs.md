# Backend (FastAPI) — framework i biblioteki (dlaczego użyte)

Ten dokument ma w zwięzły, ale „merytoryczny” sposób odpowiedzieć na pytania:
- jak backend jest zrobiony od strony **frameworku (FastAPI)**,
- jakie **biblioteki Pythona** są użyte i **dlaczego** (a nie tylko „bo są w requirements”).

Szczegółowa dokumentacja endpointów (konkretne ścieżki, payloady, kontrakty) jest celowo poza zakresem tego pliku.

---

## 1) Sposób komunikacji (krótko, jako komponent)

Backend komunikuje się przez HTTP:
- **JSON request/response** (REST-owe endpointy FastAPI),
- **serwowanie plików statycznych** dla artefaktów (np. audio, wygenerowane JSON-y) przez mechanizm `StaticFiles`.

Praktyczna konsekwencja: duże dane (audio, artefakty pipeline) są pobierane jako pliki, a API zwraca zwykle metadane + ścieżki/URL do tych plików.

---

## 2) Framework: FastAPI w tym projekcie

### 2.1 FastAPI jako aplikacja ASGI
Projekt używa FastAPI jako serwera aplikacyjnego. To daje:
- szybkie tworzenie endpointów (dekoratory `@router.get/post`),
- automatyczną walidację wejścia/wyjścia (modele Pydantic),
- dependency injection (np. sesja DB per request).

Uruchomienie odbywa się przez Uvicorn (ASGI server) — to on „hostuje” obiekt aplikacji FastAPI.

### 2.2 Entrypoint i kompozycja aplikacji
Centralnym miejscem składania aplikacji jest `app/main.py`.

Co robi `app/main.py` i dlaczego:
- **ładuje `.env` bardzo wcześnie** (żeby downstream moduły mogły czytać klucze i konfiguracje z env),
- **konfiguruje CORS** (dev-friendly integracja z frontendem),
- **rejestruje routery** (auth/users oraz moduły `air/*`),
- **montuje katalogi statyczne** (udostępnianie artefaktów pipeline bez robienia osobnych endpointów „download”),
- **tworzy tabele DB przy starcie** (`Base.metadata.create_all`) — prosty model bez migracji.

### 2.3 Routery (podział odpowiedzialności)
W projekcie stosowany jest typowy wzorzec FastAPI:
- router per obszar domeny (np. `auth`, `air/render`, `air/inventory`),
- wszystkie routery są „sklejane” w entrypoincie.

### 2.4 Dependency Injection (DI)
FastAPI DI jest użyte głównie do:
- podpinania **sesji bazy danych** (session per request),
- weryfikacji użytkownika po JWT w dependency typu `get_current_user`.

Warto wiedzieć: w repo istnieją dwa „źródła” `get_db()` (w `app/database/connection.py` i lokalnie w niektórych routerach). Funkcyjnie robią to samo: tworzą `SessionLocal`, `yield`, a na końcu `close()`.

### 2.5 Pydantic (kontrakty danych)
Pydantic jest wykorzystywany do:
- walidacji requestów (np. schemat renderu, schemat MIDI),
- serializacji odpowiedzi.

To jest kluczowe, bo pipeline operuje na złożonych strukturach JSON (meta, pattern/layers, mapy sampli), które muszą być stabilne.

### 2.6 „Best-effort” import modułów
`app/main.py` ładuje część modułów `air/*` w trybie best-effort: jeśli brakuje zależności (np. bibliotek AI) lub import rzuci wyjątek, backend nadal startuje, tylko dany router nie będzie dostępny.

Dlaczego tak:
- ułatwia developerom uruchomienie backendu bez pełnego zestawu zależności,
- pozwala trzymać opcjonalne integracje (AI) bez blokowania całego API.

---

## 3) Biblioteki i dlaczego są użyte (mapa zależności)

Poniżej opis bibliotek z `requirements.txt` w układzie: **do czego** i **gdzie** (na poziomie modułów/obszarów, bez dokumentacji endpointów).

### 3.1 Serwer i warstwa API

#### `fastapi`
Dlaczego:
- framework HTTP, routery, DI, walidacja, automatyczne OpenAPI.
Gdzie:
- cała aplikacja, entrypoint i routery.

#### `uvicorn[standard]`
Dlaczego:
- uruchamia aplikację ASGI; wariant `[standard]` wnosi typowe dodatki produkcyjne (np. lepsze zależności sieciowe/obsługa loop).
Gdzie:
- runtime serwera (start aplikacji).

#### `pydantic`
Dlaczego:
- stabilne modele request/response, walidacja złożonych struktur JSON w pipeline.
Gdzie:
- schematy w modułach `app/air/*/schemas.py`, `app/auth/schemas.py`.

#### `python-dotenv`
Dlaczego:
- szybka konfiguracja lokalna przez `.env` (klucze do providerów AI, secret JWT).
Gdzie:
- `app/main.py` (wczesne ładowanie),
- `app/air/providers/client.py` (defensywne ładowanie konfiguracji providerów).

### 3.2 Baza danych

#### `sqlalchemy`
Dlaczego:
- ORM i warstwa sesji dla SQLite; prosty model danych: użytkownicy + mapowanie projektów.
Gdzie:
- `app/database/connection.py`,
- modele w `app/auth/models.py`.

Adnotacja (ważne):
- w tym projekcie użyto **SQLite** (`sqlite:///./users.db`), ponieważ baza służy **tylko i wyłącznie** do:
	- przechowywania użytkowników,
	- przechowywania przynależności projektów do użytkowników (mapowanie user → render `run_id`).

Struktura (faktyczny schemat z modeli SQLAlchemy):
- `users`
	- `id` (PK, int)
	- `username` (unique, indexed)
	- `pin_hash` (hash PIN)
- `projs`
	- `id` (PK, int)
	- `user_id` (FK → `users.id`, nullable; projekt może być anonimowy)
	- `created_at` (datetime)
	- `render` (string; przechowuje `run_id` kroku render — traktowane jako stabilne ID projektu)

Relacja:
- `users (1) -> (N) projs` po `projs.user_id`.

Uwaga techniczna:
- obecnie DB to SQLite plikowa; dla większej skali zwykle przechodzi się na Postgres i migracje (Alembic), ale to już decyzja produktowa.

### 3.3 Uwierzytelnianie

#### `bcrypt`
Dlaczego:
- bezpieczne hashowanie PIN (projekt używa PIN jako sekretu logowania).
Gdzie:
- `app/auth/models.py` (`hash_pin`, `verify_pin`).

#### `python-jose`
Dlaczego:
- generowanie i weryfikacja JWT (HS256) bez potrzeby ciężkich frameworków auth.
Gdzie:
- `app/auth/dependencies.py` (encode/decode tokena, dependency `get_current_user`).

### 3.4 Warstwa AI (LLM providers)

#### `openai`
Dlaczego:
- dostęp do modeli OpenAI dla generowania ustrukturyzowanego JSON (parametry, MIDI).
Gdzie:
- `app/air/providers/client.py` + użycie w `param_generation` i `midi_generation`.

#### `anthropic`
Dlaczego:
- alternatywny provider LLM (Claude) — redundancja i możliwość wyboru modelu.
Gdzie:
- `app/air/providers/client.py` + wywołania w krokach generacji.

#### `google-generativeai`
Dlaczego:
- integracja z Gemini; projekt ma defensywny kod odczytu odpowiedzi (SDK ma różne formaty w zależności od wersji).
Gdzie:
- `app/air/providers/client.py` + wywołania w krokach generacji.

Ważny aspekt architektury:
- te integracje są projektowane jako „wymienne” (provider + model id), a konfiguracja w dużej mierze idzie przez zmienne środowiskowe.

### 3.5 Audio / DSP (render)

#### `numpy`
Dlaczego:
- szybkie operacje numeryczne; w renderze wykorzystywane do prostego resamplingu/pitch-shiftu.
Gdzie:
- `app/air/render/engine.py`.

#### `scipy`
Dlaczego:
- bardziej kompatybilne wczytywanie plików WAV niż wbudowany `wave` (różne formaty, dtype).
Gdzie:
- `app/air/render/engine.py` (preferowana ścieżka odczytu WAV).

#### `pydub`
Dlaczego:
- wygodne narzędzia do pracy z audio (konwersje, cięcia) — nawet jeśli nie jest krytyczne w renderze, bywa użyteczne w narzędziach i rozszerzeniach pipeline.
Gdzie:
- w repo występuje jako zależność „audio processing”; jeśli nie jest używana w runtime, nadal jest uzasadniona jako narzędzie wspierające rozwój.

### 3.6 MIDI i teoria muzyki

#### `mido`
Dlaczego:
- zapis/odczyt `.mid`; w projekcie używany opcjonalnie do eksportu artefaktu MIDI.
Gdzie:
- `app/air/midi_generation/engine.py` (jeśli `mido` dostępne).

#### `pretty_midi`
Dlaczego:
- wygodna praca na obiektach MIDI (analiza, manipulacja) — często bardziej „muzyczna” warstwa niż surowy format.
Gdzie:
- zależność przygotowana pod generację/analizę MIDI; w kodzie runtime kroku `midi_generation` kluczowy jest własny JSON + opcjonalny eksport `.mid`.

#### `music21`
Dlaczego:
- narzędzia teorii muzyki (skale, akordy, analiza) przydatne w bardziej „muzycznych” transformacjach i walidacji.
Gdzie:
- wykorzystywane głównie w eksperymentach/testach i rozszerzeniach (niekoniecznie w głównym gorącym szlaku requestów).

### 3.7 HTTP i narzędzia

#### `requests`
Dlaczego:
- proste wykonywanie HTTP requestów do zewnętrznych serwisów (np. fetcher sampli / integracje).
Gdzie:
- narzędzia/testy i potencjalne moduły pobierania danych.

#### `matplotlib`
Dlaczego:
- szybkie wykresy/diagnostyka (np. wizualizacja cech audio/MIDI) — typowo bardziej w testach i narzędziach niż w samym API.
Gdzie:
- obszar testów i narzędzi.

---

## 4) Konfiguracja i środowisko (dlaczego tak)

Projekt opiera konfigurację na `.env` i zmiennych środowiskowych, bo:
- klucze do providerów AI nie powinny być w repo,
- wybór modeli (provider/model) ma być możliwy bez zmian w kodzie,
- lokalny dev ma być szybki (jeden plik `.env`).

Kluczowe zmienne:
- `AUTH_SECRET_KEY` — sekret do podpisu JWT,
- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `OPENROUTER_API_KEY` — klucze providerów,
- `*_MODEL` / `*_MODELS` — wybór modelu lub lista modeli.

---

## 5) Najważniejsze decyzje techniczne (z perspektywy bibliotek)

- **Plikowe artefakty pipeline**: zamiast trzymać duże dane w DB, projekt trzyma je na dysku i serwuje jako statyczne pliki.
- **SQLite + SQLAlchemy**: minimalny koszt uruchomienia i prosty model danych (user/proj).
- **Pydantic jako kontrakt**: struktury JSON pipeline są stabilizowane przez modele.
- **Wymienne providery AI**: biblioteki OpenAI/Anthropic/Gemini są „adapterami” pod wspólny cel (zwrot JSON).

---

## 6) Gdzie zacząć czytanie kodu (pod framework + biblioteki)

Szybka ścieżka „żeby zrozumieć dlaczego te biblioteki tu są”:
- `app/main.py` — kompozycja FastAPI + wczesne `.env` + static mounts + best-effort import,
- `app/air/providers/client.py` — jak i dlaczego inicjalizowane są klienci AI,
- `app/auth/dependencies.py` i `app/auth/models.py` — JWT + bcrypt,
- `app/database/connection.py` — SQLAlchemy/SQLite,
- `app/air/render/engine.py` — numpy/scipy w praktyce.
