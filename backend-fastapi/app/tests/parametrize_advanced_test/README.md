# Parametrized Advanced Test Pipeline (MIDI → Samples → Audio)

Ten moduł demonstruje uproszczony, mocno instrumentowany pipeline generatywny z etapami:
1. Generacja struktury MIDI
2. Zapis do pliku MIDI
3. (Opcjonalnie) Wizualizacja pianoroll → PNG + base64
4. Wybór sampli (symulacja)
5. Render audio (placeholder sinus)
6. Zbieranie szczegółowych zdarzeń debug

---
## Struktura modułu

Katalog: `backend-fastapi/app/tests/parametrize_advanced_test/`

| Plik | Rola |
|------|------|
| `parameters.py` | Definicje parametrów wejściowych (dataclasses) + presety |
| `midi_engine.py` | Generacja patternu MIDI + zapis do pliku `pattern.mid` |
| `midi_visualizer.py` | Budowa pianoroll (`pianoroll.png`) + base64 |
| `sample_library.py` | Symulacja wyboru sampli |
| `audio_renderer.py` | Render prostej fali sinus do WAV |
| `pipeline.py` | Orkiestracja etapów i logowanie zdarzeń |
| `debug_store.py` | In‑memory store runów i eventów |
| `router.py` | Endpointy FastAPI (`/param-adv/...`) |
| `output/` | Artefakty (`pattern.mid`, `pianoroll.png`, pliki audio) |

---
## Przepływ wykonania (run_full)
Body (skrócone, pojedynczy obiekt):
```json
{
  "midi": { "genre": "ambient", "tempo": 80, ... },
  "audio": { "seconds": 6.0, ... },
  "samples": { ... } // opcjonalne
}
```

1. `pipeline.run_full()`
   - `DEBUG_STORE.start()` → `run_id`
   - Logi: `module_version`, `params_received`
   - Etapy: `generate_midi` → `save_midi` → `generate_pianoroll` → `select_samples` → `render_audio`
   - Zakończenie: `run.completed`
2. Odpowiedź (warstwowe artefakty):
```json
{
  "run_id": "...",
  "midi": { "pattern": [...], "layers": {"piano": [...], ...}, "meta": {...} },
  "samples": { ... },
  "audio": { "audio_file": "..." },
  "midi_file": ".../pattern.mid" | {"combined": "...", "layers": {"piano": "...", ...}},
  "midi_image": { "path": ".../pianoroll.png", "base64": "iVBORw0..." },
  "midi_images": { "combined": {...}, "layers": {"piano": {...}, ...} },
  "debug": { "run_id": "...", "events": [ ... ] }
}
```

---
## Generacja MIDI — `midi_engine.py`
`generate_midi(params, log)`:
| Krok | Opis |
|------|------|
| Seed | Ustalany jeśli `params.seed` (deterministyczność) |
| Skala | Mapowanie `key + scale` → `SCALE_NOTES` |
| Pętla | `bars` × 8 kroków, prawd. 0.7 że powstanie nuta |
| Logi | `seed_initialized`, `scale_resolved`, `bar_composed`, `pattern_generated`, `pattern_stats` |

Struktura patternu:
```json
{
  "pattern": [ { "bar": 0, "events": [ {"step":0,"note":60,"vel":90,"len":1}, ... ] }, ... ],
  "meta": { "tempo": 80, "instruments": ["piano", ...] }
}
```

### Zapis MIDI — `save_midi(midi_data, log)`
- Używa `mido` (fallback jeśli brak → `mido_missing`).
- Serializuje każdą nutę do `note_on/note_off`.
- Logi per takt: `bar_serialized`; końcowo `midi_file_saved`.

---
## Wizualizacja — `midi_visualizer.py`
`generate_pianoroll(midi_data, log)` oraz `generate_pianoroll_layers(midi_data, log)`:
- Jeśli brak `matplotlib` → `pianoroll_skipped`.
- Siatka: Y = nuty (min..max), X = kroki (bars * 8).
- `imshow(cmap='magma')` + zapis `pianoroll.png` + base64.
- Log: `pianoroll_generated` (liczba nut, rozmiar pliku).

---
## Przygotowanie sampli — `sample_adapter.py`
`prepare_samples(instruments, genre, log)`:
- Adapter korzystający z istniejących narzędzi testowych do pobrania/wygenerowania WAV per instrument.
- Zwraca mapowanie instrument → plik WAV w `output/samples`.

### Wysokiej jakości sample (Freesound)
- Jeśli ustawisz zmienną środowiskową `FREESOUND_API_KEY`, selektor skorzysta z Freesound API do wyszukiwania rzeczywistych sampli (preferowane WAV) na podstawie `genre` oraz biasów z `mood`.
- Jeśli brak klucza → fallback do sampli wbudowanych (syntetyczne placeholdery).

Konfiguracja (Windows PowerShell):

```powershell
# 1) Ustaw klucz API na bieżącą sesję
$env:FREESOUND_API_KEY = "<TWOJ_TOKEN>"

# 2) (opcjonalnie) Sprawdź dostępność w backendzie
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/param-adv/meta"

# 3) Uruchom pipeline jak zwykle
```

Wymagania do konwersji preview (gdy oryginalny WAV jest niedostępny lub wymaga zalogowanego pobrania):
- `pydub` (już w requirements.txt)
- `ffmpeg` w PATH systemowym (Windows: zainstaluj np. z https://www.gyan.dev/ffmpeg/builds/ i dodaj katalog `bin` do PATH).

Uwagi licencyjne:
- Korzystając z Freesound pamiętaj o licencji sampli i atrybucji – wyniki wyszukiwania zawierają pole `license`.

---
## Rendering audio — `audio_renderer.py`
`render_audio(audio_params, midi_data, sample_data, log)`:
- Render na podstawie sampli per instrument z prostym pitch‑shiftingiem i miksowaniem.
- Fallback do sinusa jeśli brak sampli.
- Logi progresu + `audio_file_saved`.

---
## Orkiestracja — `pipeline.py`
Tryby: `run_midi`, `run_render`, `run_full`.
Logi wysokiego poziomu (`stage=run`):
`midi_phase` / `render_phase` / `full_pipeline`, następnie `params_received`, `midi_generated`, `samples_selected`, `audio_rendered`, `completed`.

Logi kontrolne:
- `stage=func` → `enter` / `exit`
- `stage=call` → zamiar wywołania kolejnej funkcji

---
## Debug Store — `debug_store.py`
- `start()` → nowy run
- `log()` → dopisuje event z timestamp
- Endpoint `/param-adv/debug/{run_id}` → pełna lista eventów

---
## Endpointy — `router.py`
| Metoda | Ścieżka | Opis |
|--------|---------|------|
| GET | `/param-adv/presets` | Presety parametrów |
| POST | `/param-adv/run/midi` | Tylko generacja MIDI + pianoroll |
| POST | `/param-adv/run/render` | MIDI + samples + audio |
| POST | `/param-adv/run/full` | Pełny pipeline |
| GET | `/param-adv/debug/{run_id}` | Logi debug |

`/param-adv/meta` sygnalizuje schemat payloadu i opcjonalność `samples`.

---
## Frontend (strona `param-adv`)
- Polling 1s endpointu debug do `run.completed`.
- `midi_image.base64` → `<img>` (pianoroll).
- Układ: Presety → Parametry → Run → Pianoroll → Debug timeline.

---
## Kategorie logów
| stage | Znaczenie |
|-------|-----------|
| run | Etapy wysokiego poziomu |
| midi | Generacja patternu i zapis |
| samples | Dobór sampli |
| audio | Render dźwięku |
| func | Wejście/wyjście funkcji |
| call | Wywołanie kolejnych etapów |
| meta | Informacje kontekstowe |

---
## Rozszerzenia (planowane / możliwe)
- Unikalne nazwy artefaktów per `run_id`
- Pobieranie plików (download endpoints)
- `LOG_LEVEL` filtrowanie logów
- SSE / WebSocket
- Grupowanie + kolorowanie timeline
- Trimming długich pól JSON

---
## Przykłady wywołań

PowerShell (Invoke-RestMethod):

```powershell
$body = @{ 
  midi = @{ genre = 'ambient'; mood = 'calm'; tempo = 100; key = 'C'; scale = 'major'; instruments = @('piano','pad'); bars = 4 }
  audio = @{ sample_rate = 44100; seconds = 4.0; master_gain_db = -3.0 }
} | ConvertTo-Json -Depth 6

Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/param-adv/run/full" -Method POST -Body $body -ContentType 'application/json'
```

curl:

```bash
curl -X POST http://127.0.0.1:8000/api/param-adv/run/full \
  -H 'Content-Type: application/json' \
  -d '{
    "midi": {"genre":"ambient","mood":"calm","tempo":80,"key":"C","scale":"major","instruments":["piano"],"bars":4},
    "audio": {"sample_rate":44100,"seconds":4.0,"master_gain_db":-3.0}
  }'
```

---
## Diagnostyka
Jeśli brak `run_id` lub pojawia się 422 (Field required: samples):
1. `/api/debug/routes` (czy router załadowany)
2. Sprawdź `/api/param-adv/meta` — powinno zwrócić `payload = "single-object"` oraz `samples_optional = true`.
3. Prefix `/api/param-adv/...`
4. Walidacja JSON (czy wysyłasz jeden obiekt z kluczami `midi` i `audio`)
5. Raw response w UI

---
## Uwaga
Kod demonstracyjny – generacja i audio są uproszczone. Logi przy dużych wartościach `bars` mogą rosnąć wykładniczo objętościowo.
