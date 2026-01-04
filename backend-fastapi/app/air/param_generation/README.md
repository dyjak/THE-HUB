# AIR (backend) — `param_generation`

Ten moduł odpowiada za **krok 1 pipeline AIR**: planowanie wysokopoziomowych parametrów muzycznych na podstawie promptu użytkownika.

To jest warstwa „meta” — moduł **nie generuje MIDI** i nie renderuje audio. Jego wyjście ma być ustrukturyzowany JSON (głównie pole `meta`), który jest później używany jako wejście do `midi_generation` i `render`.

## 1. Pliki w module

- [router.py](router.py) — endpointy HTTP, budowa promptów, wywołanie LLM, zapis outputów, proxy do inventory, endpointy PATCH.
- [schemas.py](schemas.py) — walidacja wejścia (`ParameterPlanIn`) oraz normalizacja instrumentów i `instrument_configs`.
- [debug_store.py](debug_store.py) — prosty debug store w pamięci procesu (`run_id` → lista zdarzeń).
- `output/` — katalog na wyniki generacji (`parameter_plan_raw.txt`, `parameter_plan.json`).

## 2. Rola w pipeline

1. Frontend wysyła prompt i opcjonalne wartości startowe (tempo, metrum, instrumenty).
2. Backend buduje:
   - system prompt (restrykcyjny opis roli + schema JSON + ograniczenia),
   - user payload (minified JSON zawierający `user_prompt`).
3. Backend woła wybranego providera LLM (OpenAI / Anthropic / Gemini / OpenRouter).
4. Backend próbuje sparsować odpowiedź do JSON i zapisuje pliki w `output/<UTC_YYYYMMDD_HHMMSS>_<run_id>/`.
5. Frontend edytuje parametry oraz wybiera konkretne sample z inventory (przez endpointy proxy w tym module).

## 3. Endpointy HTTP

Prefiks routera: `/api/air/param-generation`

### 3.1. Dostawcy i modele

- `GET /providers`
  - Zwraca listę dostępnych providerów z `app/air/providers/client.py`.

- `GET /models/{provider}`
  - Zwraca listę modeli dla providera.
  - Backend deduplikuje i czyści nazwy modeli (żeby UI mogło używać ich jako kluczy).

### 3.2. Proxy do inventory (lista instrumentów i sampli)

- `GET /available-instruments`
  - Jeśli inventory jest dostępne, zwraca listę instrumentów z inventory.
  - Jeśli nie, zwraca pustą listę.

- `GET /samples/{instrument}?offset=0&limit=100`
  - Zwraca listę sampli z inventory dla danego instrumentu.
  - Obsługuje agregatory:
    - `drums` / `drumkit` → instrumenty perkusyjne wyciągnięte z kategorii `Drums` w inventory,
    - `fx` → instrumenty wyciągnięte z kategorii `FX` w inventory.
  - Dla „normalnych” nazw instrumentów robi mapowanie przez `_resolve_target_instruments()` (synonimy, pluralizacja, case-insensitive, dopasowanie po prefiksie).

Odpowiedź zawiera m.in. `items[].url` w formacie `/api/local-samples/<file_rel>`, żeby UI mogło odtwarzać sample po HTTP.

### 3.3. Generowanie planu

- `POST /plan`

Request body (`ParameterPlanRequest` w `router.py`):

```jsonc
{
  "parameters": {
    "prompt": "epicki soundtrack 90 BPM z chórem i smyczkami",
    "style": "ambient",
    "mood": "calm",
    "tempo": 80,
    "key": "C",
    "scale": "major",
    "meter": "4/4",
    "bars": 16,
    "length_seconds": 180,
    "dynamic_profile": "moderate",
    "arrangement_density": "balanced",
    "harmonic_color": "diatonic",
    "instruments": ["piano", "pad", "strings"],
    "instrument_configs": []
  },
  "provider": "gemini",
  "model": "gemini-3-pro-preview",
  "project_id": "optional-stable-id"
}
```

W środku `parameters` backend waliduje dane przez `ParameterPlanIn` (Pydantic). Jeśli nie podasz części pól, zostaną użyte wartości domyślne.

Response (uproszczony; backend zwraca więcej pól):

```jsonc
{
  "run_id": "a1b2c3d4e5f6",
  "system": "...",
  "user": "{\"task\":\"plan_music_parameters\",\"user_prompt\":...}",
  "raw": "...",
  "parsed": {"meta": {"tempo": 90, "instruments": [...], "instrument_configs": [...]}},
  "errors": ["parse: ..."],
  "saved_raw_rel": "20260104_120000_a1b2c3d4e5f6/parameter_plan_raw.txt",
  "saved_json_rel": "20260104_120000_a1b2c3d4e5f6/parameter_plan.json",
  "project_id": "optional-stable-id"
}
```

Uwagi:

- Jeśli parsowanie JSON się nie uda, `parsed` będzie `null`, a `errors` będzie zawierać listę błędów.
- Jeśli `parsed` jest słownikiem, backend dopisuje `parsed.user_prompt`, żeby zachować oryginalny prompt niezależnie od późniejszych PATCH do `meta`.

### 3.4. Debug i odtwarzanie planu

- `GET /debug/{run_id}`
  - Zwraca zdarzenia debugowe zapisane w pamięci procesu.
  - Dane nie są trwałe (znikają po restarcie backendu).

- `GET /plan/{run_id}`
  - Szuka folderu `output/*_<run_id>/parameter_plan.json`.
  - Czyta JSON „defensywnie”: jeśli plik zawiera śmieci na końcu, backend próbuje znaleźć **najdłuższy poprawny prefiks JSON** (od pierwszej `{` do końca tekstu).

### 3.5. Aktualizacja planu przez frontend (PATCH)

- `PATCH /plan/{run_id}/selected-samples`
  - Aktualizuje `meta.selected_samples` w zapisanym `parameter_plan.json`.
  - To jest powiązanie instrument → `sample_id` z inventory.

Przykładowy payload:

```json
{"selected_samples":{"Piano":"Instruments/Piano/Piano 1.wav","Kick":"Drums/Kick/..."}}
```

- `PATCH /plan/{run_id}/meta`
  - Nadpisuje całe `doc["meta"]` w zapisanym `parameter_plan.json`.
  - Jeśli w istniejącym pliku było `meta.selected_samples`, a frontend nie poda go w nowym `meta`, backend zachowuje to pole (żeby nie „zgubić” wyboru sampli).

## 4. Modele danych i normalizacja (Pydantic)

`schemas.py` definiuje wejściowy model `ParameterPlanIn` oraz `InstrumentConfig`.

Najważniejsze zachowania:

- `ParameterPlanIn.instruments` jest normalizowane:
  - obsługuje string `"piano,pad,strings"` i listę,
  - usuwa duplikaty,
  - filtruje tylko do `INSTRUMENT_OPTIONS`.
- `INSTRUMENT_OPTIONS` jest rozszerzane dynamicznie o instrumenty z inventory (jeśli inventory jest dostępne przy imporcie modułu).
- `ParameterPlanIn.instrument_configs` jest uzupełniane automatycznie, jeśli brakuje konfiguracji dla któregoś instrumentu.

Fragment logiki uzupełniania `instrument_configs`:

```python
@validator("instrument_configs", always=True)
def ensure_configs(cls, v, values):
    instruments = values.get("instruments", [])
    mapped = {c.name: c for c in v} if v else {}
    out = []
    for idx, inst in enumerate(instruments):
        existing = mapped.get(inst)
        if existing:
            out.append(existing)
            continue
        role = "lead" if idx == 0 else "accompaniment"
        register = "low" if inst in ("bass", "808") else "mid"
        out.append(InstrumentConfig(name=inst, role=role, register=register))
    return out
```

## 5. Jak powstaje prompt do LLM

`router.py` buduje prompt w `_parameter_plan_system(plan)`.

1) Backend buduje listę „dozwolonych instrumentów”:

- preferuje listę z inventory (`list_instruments()`),
- fallback: krótka, ręczna lista.

2) System prompt:

- wymusza odpowiedź jako **minified JSON**,
- opisuje schema wyjściowego JSON,
- wymusza spójność `instruments` i `instrument_configs`.

3) User payload:

```python
user = json.dumps(
    {"task": "plan_music_parameters", "user_prompt": plan.prompt},
    separators=(",", ":"),
    ensure_ascii=False,
)
```

## 6. Parsowanie JSON (odporność na błędy)

### 6.1. Parsowanie odpowiedzi LLM

Backend używa `_safe_parse_json(raw)`:

- usuwa płotki markdown (jeśli model je doda),
- jeśli `json.loads()` się nie uda, próbuje uciąć tekst do ostatniej `}`,
- zwraca listę błędów zamiast jednego wyjątku.

Fragment:

```python
for attempt in range(2):
    try:
        candidate = json.loads(text)
        if isinstance(candidate, dict):
            return candidate, errors
        errors.append("parse: top-level JSON must be an object")
        return None, errors
    except Exception as e:
        if attempt == 0:
            last_brace = text.rfind("}")
            if last_brace > 0:
                text = text[: last_brace + 1]
                errors.append(f"parse: truncated to last brace due to {e}")
                continue
        errors.append(f"parse: {e}")
        break
```

### 6.2. Odczyt `parameter_plan.json` z dysku

Endpoint `GET /plan/{run_id}` (oraz oba endpointy `PATCH`) stosuje strategię odzyskiwania JSON z pliku:

- najpierw próbuje `json.loads(text)`,
- jeśli to nie działa, szuka pierwszej `{` i próbuje parsować coraz krótsze prefiksy od końca.

Cel: nie blokować edycji planu, nawet jeśli plik został lekko uszkodzony.

## 7. Persist na dysk

Każde wywołanie `POST /plan` tworzy folder:

`output/<UTC_YYYYMMDD_HHMMSS>_<run_id>/`

i zapisuje:

- `parameter_plan_raw.txt` — surowy tekst od modelu,
- `parameter_plan.json` — zparsowany JSON (tylko jeśli parsowanie się uda).

Response zwraca ścieżki względne `saved_*_rel` liczone względem katalogu `output/`.

## 8. Uwagi / edge-case’y

- `debug_store` jest in-memory: `GET /debug/{run_id}` działa tylko do restartu procesu.
- Inventory może być niedostępne (np. import się nie uda); wtedy:
  - `GET /available-instruments` zwraca pustą listę,
  - `GET /samples/{instrument}` zwróci 500 (`inventory_unavailable`).
- Instrumenty są w praktyce mieszanką nazw z `INSTRUMENT_OPTIONS` (z `schemas.py`) i nazw z inventory.
  - `schemas.py` filtruje `parameters.instruments` po `INSTRUMENT_OPTIONS`.
  - `router.py` w system prompt próbuje narzucić listę instrumentów z inventory (jako “allowed list” dla modelu), ale to jest tylko wskazówka dla LLM.
  - Ten moduł nie wymusza automatycznej normalizacji wielkości liter nazw instrumentów w `meta` — nazwy powinny być spójne między UI, planem i inventory.

## 9. Debugowanie

- Każde wywołanie `POST /plan` generuje `run_id` i zapisuje etapy w `debug_store` (start, wywołanie providera, parsowanie, persist).
- `GET /debug/{run_id}` pozwala podejrzeć pełną historię wywołania.

## 10. Domyślne wybory providerów

Jeśli w request nie podasz `provider`/`model`, backend ma fallbacki:

- Provider domyślny: `gemini`.
- OpenAI: `OPENAI_MODEL` lub `gpt-4o-mini`, `temperature=0.0`.
- Anthropic: `ANTHROPIC_MODEL` lub `claude-3-5-haiku-latest`, `temperature=0.0`.
- Gemini: `GOOGLE_MODEL` lub `gemini-3-pro-preview`.
- OpenRouter: `OPENROUTER_MODEL` lub `meta-llama/llama-3.1-8b-instruct:free`, `temperature=0.0`.

## 11. Szybkie podsumowanie

- `param_generation` generuje plan parametrów (meta), nie MIDI.
- `POST /plan` zapisuje raw + (jeśli się da) JSON do `output/<timestamp>_<run_id>/`.
- Proxy `/available-instruments` i `/samples/{instrument}` upraszcza integrację UI z inventory.
- Endpointy `PATCH` utrzymują `parameter_plan.json` jako źródło prawdy dla UI (zwłaszcza `meta.selected_samples`).

