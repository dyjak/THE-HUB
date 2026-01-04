# AIR (backend) — `midi_generation`

Ten moduł odpowiada za **krok 2 pipeline AIR**: wygenerowanie struktury MIDI (w formacie JSON) na podstawie `meta` z kroku `param_generation`.

To jest krok „kompozycji / aranżacji” na siatce czasu — moduł **nie renderuje audio**. Jego output jest później wejściem do `render`.

## 1. Pliki w module

- [router.py](router.py) — endpointy HTTP, wywołanie LLM (kompozytora), linkowanie `param_run_id` do renderu.
- [engine.py](engine.py) — normalizacja struktury MIDI, zapis artefaktów do `output/`, rozbijanie per instrument.
- [schemas.py](schemas.py) — modele Pydantic wejścia/wyjścia (`MidiGenerationIn`, `MidiGenerationOut`).
- `output/` — katalog z artefaktami wygenerowanymi na dysku.

## 2. Rola w pipeline

1. Frontend bierze `parsed.meta` z `param_generation`.
2. Frontend wywołuje `POST /api/air/midi-generation/compose` z:
   - `meta` (tempo/key/scale/bars/instruments/instrument_configs),
   - opcjonalnie `provider`/`model`.
3. Backend (jeśli nie podano `ai_midi`) wywołuje LLM, który zwraca JSON z polami `pattern` i/lub `layers`.
4. `engine.generate_midi_and_artifacts()`:
   - dopina brakujące pola (`meta`, `layers`, `pattern`),
   - zapisuje `midi.json`, opcjonalnie `midi.mid` i `pianoroll.svg`,
   - tworzy pliki per-instrument (`midi_<inst>.json`, itd.).
5. Backend zwraca `run_id` i ścieżki do artefaktów.

## 3. Endpointy HTTP

Prefiks routera: `/api/air/midi-generation`

### 3.1. `POST /compose`

Główny endpoint generacji.

Request (`MidiGenerationIn`):

```jsonc
{
  "meta": {
    "style": "ambient",
    "mood": "calm",
    "tempo": 80,
    "key": "C",
    "scale": "major",
    "meter": "4/4",
    "bars": 16,
    "length_seconds": 180.0,
    "dynamic_profile": "moderate",
    "arrangement_density": "balanced",
    "harmonic_color": "diatonic",

    "user_prompt": "... opcjonalnie ...",
    "instruments": ["Piano", "Kick", "Snare"],
    "instrument_configs": [
      {"name": "Piano", "role": "Lead"},
      {"name": "Kick", "role": "Percussion"}
    ],
    "seed": null
  },
  "provider": "gemini",
  "model": "...",
  "param_run_id": "opcjonalny_run_id_z_param_generation",

  // opcjonalnie: pomija LLM i używa tego JSON-a (debug/eksperymenty)
  "ai_midi": null
}
```

Response (`MidiGenerationOut`, skrót):

```jsonc
{
  "run_id": "a1b2c3d4e5f6",
  "midi": {"meta": {...}, "pattern": [...], "layers": {...}},
  "artifacts": {
    "midi_json_rel": "20260104_120000_a1b2c3d4e5f6/midi.json",
    "midi_mid_rel": "20260104_120000_a1b2c3d4e5f6/midi.mid",
    "midi_image_rel": "20260104_120000_a1b2c3d4e5f6/pianoroll.svg"
  },
  "midi_per_instrument": {"Piano": {...}, "Kick": {...}},
  "artifacts_per_instrument": {
    "Piano": {"midi_json_rel": ".../midi_Piano.json", "midi_mid_rel": "...", "midi_image_rel": "..."}
  },

  "provider": "gemini",
  "model": "...",
  "errors": ["parse: ..."],

  "system": "...",
  "user": "{...}",
  "raw": "...",
  "parsed": {"pattern": [...], "layers": {...}, "meta": {...}}
}
```

Uwagi:

- Jeśli `ai_midi` jest podane, backend nie wywołuje LLM.
- `errors` zawiera ostrzeżenia z parsowania odpowiedzi modelu (best-effort).
- `param_run_id` nie zmienia struktury outputu MIDI — służy tylko do późniejszego eksportu (linkowanie kroków).

### 3.2. `GET /run/{run_id}`

Zwraca zapisany stan MIDI dla danego `run_id` z dysku.

Jak działa wyszukiwanie:

- `router.py` przeszukuje `output/*_<run_id>/midi.json` (sufiks folderu to `_<run_id>`).
- Jeśli folder istnieje, odczytuje `midi.json` oraz best-effort wykrywa, czy istnieją:
  - `midi.mid`, `pianoroll.svg`,
  - `midi_*.json` (per instrument), oraz pasujące `midi_<inst>.mid` i `pianoroll_<inst>.svg`.

Uwagi:

- Ten endpoint odtwarza stan z plików na dysku: zwraca `midi` oraz `artifacts`.
- Pola związane z wywołaniem LLM (`provider`, `model`, `system`, `user`, `raw`, `errors`) nie są tu odtwarzane i będą `null`.

## 4. Format danych MIDI (JSON)

Kontrakt JSON jest oparty o dwa pola:

- `pattern`: lista taktów (`bar`) z listą eventów.
- `layers`: słownik `InstrumentName -> pattern` (także lista taktów z eventami).

Każdy event ma siatkę 8 kroków na takt:

- `step`: 0..7
- `note`: MIDI note number (int)
- `vel`: velocity 0..127
- `len`: długość w „krokach” (1 = ósemka, 2 = ćwierćnuta)

W system prompt LLM jest instruowany, żeby perkusja trafiała do `pattern`, a instrumenty melodyczne do `layers`.

## 5. Wywołanie LLM (kompozytor)

`router.py` buduje system prompt i user payload w `_call_composer(provider, model, meta)`.

User payload jest minified JSON:

```python
user_payload = {"task": "compose_midi_pattern", "meta": meta}
user = json.dumps(user_payload, separators=(",", ":"), ensure_ascii=False)
```

Temperatura jest ustawiona na `0.2` (celowo: trochę kreatywności, ale nadal preferencja na JSON).

Domyślne modele per provider (fallbacki z env):

- OpenAI: `OPENAI_MIDI_MODEL` → `OPENAI_MODEL` → `gpt-4o-mini`
- Anthropic: `ANTHROPIC_MIDI_MODEL` → `ANTHROPIC_MODEL` → `claude-3-5-haiku-latest`
- Gemini: `GOOGLE_MIDI_MODEL` → `GOOGLE_MODEL` → `gemini-3-pro-preview`
- OpenRouter: `OPENROUTER_MIDI_MODEL` → `OPENROUTER_MODEL` → `meta-llama/llama-3.1-8b-instruct:free`

## 6. Parsowanie i odporność na błędy

### 6.1. Parsowanie odpowiedzi LLM

`engine._safe_parse_midi_json(raw)`:

- usuwa ``` fences (jeśli model mimo instrukcji je doda),
- przy błędzie próbuje uciąć tekst do ostatniej `}`.

Fragment:

```python
for attempt in range(2):
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj, errors
        errors.append("parse: top-level JSON must be object")
        return {}, errors
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

### 6.2. Normalizacja struktury

`engine._ensure_midi_structure(meta, midi_data)` gwarantuje minimalną spójność:

- dopina `midi_data.meta` (tempo/bars/instruments/itd.) z wejściowego `meta`,
- jeśli brak `layers` → tworzy `{}`,
- jeśli brak `pattern` → buduje `pattern` jako sumę eventów ze wszystkich warstw (`layers`).

To powoduje, że downstream (`render`, UI) dostaje prawie zawsze przewidywalny kształt danych.

## 7. Artefakty na dysku

`engine.generate_midi_and_artifacts()` zapisuje wyniki do:

`output/<UTC_YYYYMMDD_HHMMSS>_<run_id>/`

Pliki globalne:

- `midi.json` — główny JSON MIDI (meta + layers + pattern)
- `midi.mid` — opcjonalnie, jeśli jest zainstalowane `mido` (best-effort)
- `pianoroll.svg` — best-effort podgląd pianoroll (SVG)

Pliki per-instrument:

- `midi_<inst>.json`
- `midi_<inst>.mid` (opcjonalnie)
- `pianoroll_<inst>.svg` (best-effort)

Dodatkowy plik zbiorczy (best-effort):

- `midi_per_instrument.json` — mapa `{instrument -> midi_json}`

### 7.1. Jak zbudować URL do pliku z `*_rel`

W tym repo `output/` dla MIDI jest wystawione statycznie (FastAPI mount) pod:

`/api/midi-generation/output`

To oznacza:

- jeśli backend zwróci `midi_json_rel = "20260104_120000_<run_id>/midi.json"`,
  to URL w przeglądarce to:

`/api/midi-generation/output/20260104_120000_<run_id>/midi.json`

Uwaga (Windows): wartości `*_rel` są budowane przez `str(Path.relative_to(...))`, więc mogą zawierać separator `\`. W kliencie HTTP/URL należy zamienić `\` na `/`.

## 8. Rozbijanie per instrument (ważne dla UI i renderu)

`engine.generate_midi_and_artifacts()` buduje `midi_per_instrument` dwoma strategiami:

1) **Instrumenty melodyczne** (gdy istnieją w `layers`)

- Dla każdego klucza w `layers` tworzy osobny `inst_midi` zawierający tylko tę warstwę.
- `pattern` jest budowany z tej pojedynczej warstwy.

2) **Perkusja** (gdy instrumenty perkusyjne są tylko w `pattern`)

- Określa, które instrumenty są perkusją na podstawie `instrument_configs[].role == "Percussion"`.
- Dla każdego z tych instrumentów filtruje globalny `pattern` po nutach GM.

Mapowanie przykładowe (fragment, w `engine._notes_for_percussion_instrument`):

```python
direct = {
    "kick": [36],
    "snare": [38],
    "clap": [39],
    "hat": [42, 46],
    "crash": [49],
    "ride": [51],
    "808": [35],
}
```

Jeśli po filtracji instrument nie ma żadnych eventów, backend nie „dorysowuje” nut — ewentualnie normalizuje liczbę taktów do pustych barów (żeby UI miało stabilny widok osi czasu).

## 9. Linkowanie `param_run_id` do projektu renderu (eksport)

`router.compose()` wykonuje best-effort linkowanie:

- jeśli request ma `param_run_id`, to backend zapisuje mapowanie `render_run_id -> param_run_id` przez `app.air.export.links.link_param_to_render(run_id, param_run_id)`.

W tej aplikacji przyjęto konwencję, że:

- `midi_run_id` == `render_run_id` (to ten sam identyfikator projektu),
- `param_run_id` jest osobnym ID i jest dołączany przez link w export.

## 10. Szybkie podsumowanie

- `POST /compose` generuje JSON MIDI i zapisuje artefakty na dysku.
- `GET /run/{run_id}` pozwala odtworzyć stan kroku z dysku.
- `engine` robi dużo „best-effort”: brak `.mid` albo `.svg` nie powinien zablokować całego pipeline.
