# AIR (backend) — `providers`

Ten moduł jest wspólną warstwą integracji z dostawcami LLM używaną przez kroki AIR, głównie:

- `param_generation` (plan parametrów + selected_samples)
- `midi_generation` (kompozycja JSON MIDI)

Nie jest to router FastAPI. To **helpery-klienty** + funkcje listujące providery/modele dla UI.

## 1. Pliki w module

- [client.py](client.py) — inicjalizacja SDK, wczytanie `.env`, zwracanie klientów, listowanie providerów i modeli.

## 2. Ładowanie konfiguracji (`.env`)

`client.py` ładuje zmienne środowiskowe jednorazowo przy imporcie modułu:

- jeśli istnieje `backend-fastapi/.env` → `load_dotenv(dotenv_path=..., override=False)`
- w przeciwnym razie → `load_dotenv()`

Konsekwencje:

- wartości ustawione w systemowym ENV mają pierwszeństwo (bo `override=False`), a `.env` tylko je uzupełnia.
- błędy w `.env` nie powinny wywrócić aplikacji — w razie problemów jest fallback.

## 3. Wspierani providerzy

Moduł wspiera 4 identyfikatory providerów (spójne z UI i routerami AIR):

- `openai`
- `anthropic`
- `gemini` (Google Generative AI)
- `openrouter` (OpenAI-compatible API)

Dla każdego providera trzymamy dwa rodzaje konfiguracji:

- **API keys / base URL** — do stworzenia klienta SDK
- **modele** — domyślny model i opcjonalna lista modeli

## 4. Publiczne API (funkcje)

### 4.1. `ChatError`

`ChatError` jest wspólnym wyjątkiem warstwy providerów. Jest rzucany m.in. gdy:

- brakuje zależności (SDK nie jest zainstalowany),
- brakuje klucza API w ENV.

To celowo jest czytelny błąd “konfiguracyjny”, a nie surowy `ImportError`.

### 4.2. Klienty SDK

#### `get_openai_client()`

Wymagane ENV:

- `OPENAI_API_KEY`

Opcjonalne ENV:

- `OPENAI_BASE_URL` — jeśli używasz proxy lub kompatybilnego endpointu

Zwraca obiekt klienta `openai.OpenAI` (SDK v1.x).

#### `get_openrouter_client()`

Wymagane ENV:

- `OPENROUTER_API_KEY`

Opcjonalne ENV:

- `OPENROUTER_BASE_URL` (default: `https://openrouter.ai/api/v1`)

Technicznie to też `openai.OpenAI`, ale skonfigurowany z innym `base_url`.

#### `get_anthropic_client()`

Wymagane ENV:

- `ANTHROPIC_API_KEY`

Zwraca `anthropic.Anthropic`.

#### `get_gemini_client()`

Wymagane ENV:

- `GOOGLE_API_KEY`

Wywołuje `genai.configure(api_key=...)` i zwraca moduł/klienta `google.generativeai`.

## 5. Listowanie providerów i modeli (UI)

### 5.1. `list_providers()`

Zwraca listę providerów dla UI w formie:

```json
[{"id":"openai","name":"OpenAI","default_model":"gpt-4o-mini"}, ...]
```

Domyślne modele są sterowane ENV (z fallbackami):

- `OPENAI_MODEL` (default `gpt-4o-mini`)
- `ANTHROPIC_MODEL` (default `claude-3-5-haiku-latest`)
- `GOOGLE_MODEL` (default `gemini-3-pro-preview`)
- `OPENROUTER_MODEL` (default `meta-llama/llama-3.1-8b-instruct:free`)

### 5.2. `list_models(provider)`

Zwraca listę modeli jako `list[str]` dla danego providera.

Najważniejsze zasady:

- można **nadpisać listę** w ENV:
  - `OPENAI_MODELS`, `ANTHROPIC_MODELS`, `GOOGLE_MODELS`, `OPENROUTER_MODELS`
  - format: elementy rozdzielone przecinkami

- jeśli override nie jest ustawiony:
  - `openai`: próbuje dynamicznie pobrać `client.models.list()` i filtruje ID (zostawia głównie `gpt-*`, `o3`, `o4`; odrzuca m.in. `embedding/audio/tts/whisper/image`); fallback do krótkiej listy statycznej.
  - `gemini`: próbuje `g.list_models()` i zostawia modele wspierające `generateContent`; filtruje modele wyglądające na stricte “image” (`imagen`/`image` w nazwie); fallback do listy statycznej.
  - `anthropic`: brak publicznego endpointu listowania → lista ręczna z fallbackiem na `ANTHROPIC_MODEL`.
  - `openrouter`: lista ręczna z deduplikacją (pierwszy element to `OPENROUTER_MODEL`).

Uwaga: deduplikacja i sanity-check nazw modeli po stronie HTTP są robione w routerze `param_generation` (żeby frontend dostawał czystą listę).

## 6. Zależności

SDK są ładowane “best-effort” (importy mogą się nie udać). Żeby dany provider działał, muszą być zainstalowane odpowiednie paczki (zgodnie z `backend-fastapi/requirements.txt`) oraz muszą być ustawione klucze API.
