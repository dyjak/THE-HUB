# Parametrized Advanced Test Pipeline (MIDI → Samples → Audio)

Ten moduł demonstruje uproszczony, mocno instrumentowany pipeline generatywny z etapami (TRYB STRICT – brak syntetycznych zastępników jeśli sample nie są dostępne):
1. Generacja struktury MIDI
2. Zapis do pliku MIDI
3. (Opcjonalnie) Wizualizacja pianoroll → PNG + base64 (warstwa łączna + per‑instrument)
4. Wybór/pobranie sampli (Freesound → Wikimedia Commons → basic tylko gdy brak klucza API)
5. Render audio (wyłącznie na realnych / pobranych lub basic jeśli Freesound niedostępny) – brak sinus fallback
6. Zbieranie szczegółowych zdarzeń debug

---
## Struktura modułu

Katalog: `backend-fastapi/app/tests/parametrize_advanced_test/`

| Plik | Rola |
|------|------|
| `parameters.py` | Definicje parametrów wejściowych (dataclasses) + presety |
| `midi_engine.py` | Generacja patternu MIDI + zapis do pliku `pattern.mid` |
| `midi_visualizer.py` | Budowa pianoroll (`pianoroll.png`) + base64 |
| `sample_library.py` | (historyczne) – obecnie logika realnych źródeł w `sample_fetcher.py` |
| `audio_renderer.py` | Strict render z użyciem wybranych sampli (pitch‑shift + miks) |
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
## Przygotowanie sampli — `sample_adapter.py` (STRICT)
`prepare_samples(instruments, genre, log, mood)`:
1. Buduje listy kandydatów per instrument (Freesound – zapytania: bazowe dla gatunku + biasy mood + hints/specjalne frazy).
2. Próbuje pobrać pierwszy działający kandydat (jeśli pierwszy zawiedzie – próbuje następnych, do wyczerpania listy).
3. Jeśli wszystkie próby Freesound nie powiodą się → Wikimedia Commons (również kilka wariantów zapytań).
4. Jeśli nadal brak (i NIE mamy klucza Freesound) – używa basic wygenerowanych sampli; jeśli klucz jest ustawiony i mimo to brak skutecznego źródła → błąd (brak degradacji jakości do sinusa).

Zwraca: listę wybranych sampli wraz z plikami WAV w `output/samples/`.

### Wielostopniowe luzowanie zapytań
Sekwencja (dla każdego instrumentu), dopóki nie znajdziemy działającego pliku WAV:
1. Zapytania gatunkowe (genre‑specific base).
2. Te same + biasy mood (np. calm → soft / gentle / warm).
3. Dedykowane hints (np. `drum kit one shot wav`, `acoustic drums wav`).
4. Ogólne frazy instrument + "wav".
5. Synonimy / kategorie (np. drums → percussion, drum loop, drum beat).
6. Fallback Commons (te same warianty).
7. Basic (tylko jeśli Freesound niedostępny).

Logi (stage = samples):
- `instrument_sample_ready` – sukces pobrania
- `download_failed` – pojedynczy kandydat nie zadziałał (spróbujemy następnego)
- `instrument_no_sample` – wyczerpano kandydatów dla instrumentu
- `prepared` – podsumowanie (jeśli brak wszystkich wymaganych → błąd w dalszej części)

### Kluczowe wyjątki
- `SampleSelectionError` – brak co najmniej jednego instrumentu po wyczerpaniu wszystkich źródeł (pipeline przerywa przed renderem).
- `SampleMissingError` – etap renderu wykrył brak lub nieładowalny plik WAV (np. usunięty między etapami).

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
## Rendering audio — `audio_renderer.py` (STRICT)
`render_audio(audio_params, midi_data, sample_data, log)`:
- Każdy instrument z listy w `midi.meta.instruments` musi mieć poprawnie załadowany sample (WAV).
- Render: pitch‑shift (resample) pojedynczej próbki bazowej do nut → ADSR → miks → normalizacja.
- Jeśli brak chociaż jednego wymaganego pliku: `SampleMissingError` (brak sinus / syntetycznych zastępników).
- Logi: `render_start`, (opcjonalnie) `sample_load_failed` / `sample_missing`, `progress`, `render_done`.

---
## Orkiestracja — `pipeline.py`
Tryby: `run_midi`, `run_render`, `run_full`.
Logi wysokiego poziomu (`stage=run`):
`midi_phase` / `render_phase` / `full_pipeline`, następnie `params_received`, `midi_generated`, `samples_selected`, `audio_rendered`, `completed`.

Logi kontrolne:
 - `stage=func` → `enter` / `exit`
 - `stage=call` → zamiar wywołania kolejnej funkcji
 - Dodatkowe przy błędach sampli: `selection_failed`, `render_failed` (po ostatnich zmianach w pipeline)

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
Jeśli brak `run_id` lub pojawia się problem z samplami:
1. Sprawdź `/api/param-adv/meta` – `samples_optional` musi być `true`.
2. Zajrzyj w `/api/param-adv/debug/{run_id}` – szukaj eventów `instrument_no_sample`, `download_failed`, `selection_failed`.
3. Upewnij się, że `FREESOUND_API_KEY` ustawiony (jeśli oczekujesz realnych próbek) i że masz FFmpeg w PATH dla konwersji preview.
4. Jeśli pojedynczy instrument często zawodzi (np. drums), spróbuj innego `genre` lub usuń go z listy aby przetestować pipeline.
5. W logach backendu sprawdź ewentualne statusy HTTP Freesound (np. 403/429) – mogą blokować pobranie oryginału i preview.

Przykładowy błąd (selection):
```json
{
  "detail": "Missing samples for instruments: drums"
}
```
Przykładowy błąd (render – jeśli plik zniknął):
```json
{
  "detail": "Missing or failed samples for instruments: piano"
}
```

---
## Uwaga
Kod demonstracyjny – generacja i audio są uproszczone. Logi przy dużych wartościach `bars` mogą rosnąć wykładniczo objętościowo. Tryb STRICT rezygnuje z jakiejkolwiek degradacji jakości (brak synusa) aby wcześnie ujawnić problemy z pozyskiwaniem sampli.
