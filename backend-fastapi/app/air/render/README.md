# AIR (backend) — `render`

Ten moduł odpowiada za **krok 3 pipeline AIR**: zamianę danych MIDI + wyboru sampli (inventory) na pliki audio WAV.

W praktyce moduł:

- buduje **stem-y** (osobne WAV per instrument),
- buduje **mix** (master WAV),
- zapisuje `render_state.json`, żeby UI mogło wrócić do tego kroku.

To jest prosty renderer oparty o **wklejanie sampli** na osi czasu i **pitch-shift przez resampling**. Wiele rzeczy jest „best-effort”: brak sampla albo brak bibliotek opcjonalnych nie powinien wywrócić całego backendu.

## 1. Pliki w module

- [router.py](router.py) — endpointy HTTP: render, odczyt stanu, rekomendacje sampli.
- [engine.py](engine.py) — silnik renderu (obliczenia, miksowanie, zapis WAV).
- [schemas.py](schemas.py) — Pydantic modele request/response.
- [mini_pipeline_test.py](mini_pipeline_test.py) — narzędzie CLI do odpalenia renderu na zapisanych outputach z poprzednich kroków.
- `output/<run_id>/` — katalog wyników renderu.

## 2. Endpointy HTTP

Prefiks routera: `/api/air/render`

### 2.1. `POST /render-audio`

Renderuje audio i zwraca ścieżki do plików.

Najważniejsze pola requestu (`RenderRequest`):

- `project_name`: prefix nazw plików
- `run_id`: identyfikator projektu (w tej aplikacji zwykle równy `midi_run_id`)
- `midi`: globalny JSON MIDI (pattern/layers/meta)
- `midi_per_instrument` (opcjonalnie): dokładniejsze dane per instrument (z kroku `midi_generation`)
- `tracks`: lista `TrackSettings` (instrument, enabled, volume_db, pan)
- `selected_samples` (opcjonalnie): mapa instrument → `sample_id` z inventory
- `fadeout_seconds` (opcjonalnie): długość fade-out w voice stealing (domyślnie `0.01`)

Response (`RenderResponse`):

- `mix_wav_rel`: ścieżka do mixu
- `stems[]`: instrument + `audio_rel`
- `sample_rate`: domyślnie 44100
- `duration_seconds`: użyta długość

### 2.2. `GET /run/{run_id}`

Wczytuje `render_state.json` z `render/output/<run_id>/render_state.json` i zwraca `RenderResponse` zapisany przy poprzednim renderze.

### 2.3. `POST /recommend-samples`

Zwraca mapę instrument → rekomendowany sample na podstawie MIDI (bez renderowania i bez zapisu).

Mechanizm rekomendacji jest w `engine.recommend_sample_for_instrument()`.

## 3. Pliki output i URL-e

### 3.1. Struktura plików na dysku

`engine.py` zapisuje pliki do:

`app/air/render/output/<run_id>/`

Nazwy plików (timestamp to `int(time.time())`):

- stem: `<project_name>_<instrument>_<timestamp>.wav`
- mix: `<project_name>_mix_<timestamp>.wav`
- stan: `render_state.json` (zapisuje `request` i `response`)

### 3.2. Jak zbudować URL do audio

W `main.py` katalog `app/air/render/output` jest wystawiony statycznie pod:

`/api/audio`

Czyli finalny URL ma postać:

- `/api/audio/<run_id>/<filename>.wav`

Uwaga: `mix_wav_rel` i `stems[].audio_rel` są obecnie liczone jako ścieżki względne względem katalogu `app/air/render/` (zwykle zaczynają się od `output/...`). Żeby zbudować URL, klient powinien:

1) usunąć prefiks `output/` (lub `output\\` na Windows)
2) zamienić separatory na `/`
3) dodać prefix `/api/audio/`

Przykład:

- backend zwraca `mix_wav_rel = "output/<run_id>/song_mix_123.wav"`
- URL: `/api/audio/<run_id>/song_mix_123.wav`

## 4. Model danych renderu (Pydantic)

Zobacz [schemas.py](schemas.py).

Najważniejsze:

- `TrackSettings.volume_db` jest przeliczane na gain: $gain = 10^{db/20}$
- `TrackSettings.pan` jest constant-power:

```python
angle = (pan + 1.0) * pi / 4
left  = cos(angle)
right = sin(angle)
```

## 5. Silnik renderu — szczegółowy opis obliczeń

Poniżej opis `engine.render_audio(req)`.

### 5.1. Ustalenie czasu trwania i siatki czasu

Renderer działa przy stałym sample rate:

- `sr = 44100`

Ustalenie liczby taktów:

1) preferuje `req.midi.meta.bars` (jeśli jest int > 0)
2) fallback: szuka maksymalnego `bar` w `midi.pattern` i `midi.layers` i ustala `bars = max_bar + 1`

Liczba kroków globalnie:

- `total_steps = bars * 8` (siatka 8 kroków na takt)

Ustalenie długości utworu w sekundach:

1) preferuje `req.midi.meta.length_seconds` (jeśli w zakresie 0.5..3600)
2) fallback: `duration_sec = bars * 2.0`

Przeliczenie na próbki:

- `frames = int(sr * duration_sec)`
- `step_samples_global = int(frames / total_steps)`

Uwaga praktyczna: `step_samples_global` jest liczbą całkowitą, więc przy nietypowych długościach `duration_sec` może wystąpić drobna kwantyzacja pozycji eventów (wszystko i tak jest „na siatce”).

To oznacza, że pozycja eventu jest liczona jako:

$$start = (bar*8 + step) * step\_samples\_global$$

### 5.2. Załadowanie inventory i wybór sampli

Inventory jest ładowane raz na początku:

- `lib = discover_samples(deep=False)`

Dobór sampla dla instrumentu (`_resolve_sample_for_instrument`):

1) jeśli `selected_samples[instrument]` istnieje → szuka po ID (przez `find_sample_by_id`)
2) fallback: pierwsza istniejąca próbka w `lib[instrument]`

Ważne: renderer **nie robi automatycznej rekomendacji**. To jest celowo osobny endpoint (`/recommend-samples`).

### 5.3. Odczyt WAV i normalizacja głośności sampla

Odczyt WAV do mono (`_read_wav_mono`):

- najpierw próbuje `scipy.io.wavfile` (jeśli dostępne) i konwertuje do float [-1..1]
- fallback: `wave` (tylko 16-bit PCM)

Ważne ograniczenie: funkcja odczytu zwraca tylko próbki audio, ale **renderer nie używa sample-rate z pliku WAV** (zmienna `sr` jest na sztywno ustawiona na 44100). W praktyce sample powinny mieć 44100 Hz, inaczej odtworzenie będzie miało złą prędkość/pitch.

Jeśli inventory ma `sample.gain_db_normalize`, renderer mnoży sample przez:

$$gain = 10^{(gain\_db\_normalize/20)}$$

### 5.4. Wybór warstwy MIDI dla instrumentu

Dla każdego tracka renderer wybiera źródło eventów:

- jeśli `req.midi_per_instrument[instrument]` istnieje:
  - preferuje `inst_midi["pattern"]` (często dla perkusji)
  - fallback: `inst_midi.layers[instrument]`
- w przeciwnym razie: `req.midi.layers[instrument]`

### 5.5. Korekta indeksu taktów (cisza na początku)

W kodzie jest mechanizm naprawiający historyczny problem, gdy generator MIDI numerował takty od `1`.

Jeśli minimalny `bar` w warstwie wynosi dokładnie `1`, renderer stosuje przesunięcie `min_bar = 1` i odejmuje je przy obliczeniu `b`.

### 5.6. Pitch shifting dla instrumentów melodycznych (mechanizm z `tanh`)

Perkusja jest wykrywana po nazwie instrumentu (`perc_set`) i **nie jest pitchowana**.

Dla instrumentów melodycznych renderer próbuje wyznaczyć naturalną wysokość sampla:

- jeśli `sample.root_midi` jest dostępne (z inventory, np. z FFT), przyjmuje `base_midi = round(root_midi)`
- inaczej używa fallbacku `_BASE_FREQ = 261.63` (C4) i przelicza na `base_midi`

Zamiast twardego clampowania nut do okna, renderer kompresuje różnicę półtonów:

- `raw_semi = target_midi - base_midi`
- wybiera `max_semi` zależnie od instrumentu (np. basy 7, piano/pads/strings 24, default 18)
- kompresja:

$$compressed = \tanh(raw\_semi/max\_semi) * max\_semi$$

Potem:

- $ratio = 2^{(compressed/12)}$
- `target_freq_eff = base_freq * ratio`

I pitch-shift realizowany jest przez `_pitch_shift_resample()` (resampling z interpolacją liniową w numpy).

Cel tego mechanizmu:

- małe interwały są prawie liniowe (zgodne z MIDI),
- bardzo duże skoki nie robią „odlotu” o kilka oktaw (bo `tanh` dąży do ±1).

### 5.7. Voice stealing (fade-out ogona)

Renderer utrzymuje `last_event_end` w próbkach.

Jeśli nowy event startuje zanim poprzedni „skończył” (`last_event_end > start`), renderer:

1) robi krótki liniowy fade-out istniejącego ogona w zakresie `fade_len = min(int(fadeout_seconds*sr), last_event_end-start)`
2) resztę ogona (po fade) czyści do zera

Daje to dwa efekty:

- unika „klików” (brak twardego ucięcia w 1 próbce),
- ogranicza długie nakładanie się ogonów.

### 5.8. Envelope nowej nuty

Dla każdej wklejanej nuty renderer stosuje prosty envelope:

- attack: 0.01 s
- release: 0.1 s

W praktyce (w próbkach):

- `a = int(0.01 * sr)`
- `r = int(0.1 * sr)`

Amplitude jest mnożona przez `vel/127` i envelope.

Uwaga: renderer **nie używa pola `len` z eventu MIDI** do skracania/dopasowania czasu trwania nuty. Długość nuty wynika z długości sampla po pitch-shifcie (`nl = len(pitched)` ograniczone do końca bufora) oraz z voice stealing (kolejny event może wyciąć ogon poprzedniego).

### 5.9. Volume i pan, zapis stemów

Po zbudowaniu mono bufora `buf` renderer tworzy stereo stem:

- `gain = 10^(volume_db/20)`
- `(pan_l, pan_r)` z constant-power
- `stem_l[i] = buf[i] * gain * pan_l`
- `stem_r[i] = buf[i] * gain * pan_r`

Stem jest zapisywany przez `_write_wav_stereo()` jako 16-bit PCM.

### 5.10. Mixdown i normalizacja

Mix stereo jest budowany jako suma stemów osobno dla lewego i prawego kanału.

`_mix_tracks()` sumuje sample i robi prostą normalizację do piku 0.9:

- `peak = max(abs(out))`
- `scale = 0.9 / peak`
- `out *= scale`

Potem zapis mixu jako WAV.

Uwaga: normalizacja jest liczona **osobno dla lewego i prawego kanału** (bo `_mix_tracks()` jest wołane osobno dla listy kanałów L i R). To może minimalnie zmienić balans stereo w porównaniu do normalizacji wspólnym pikiem stereo.

### 5.11. Błędy

Jeśli żaden stem nie powstał (np. brak sampli dla wszystkich instrumentów), renderer rzuca:

- `RuntimeError({"error":"render_no_instruments", ...})`

Router zamienia to na HTTP 500 z `detail.error = "render_failed"`.

## 6. Rekomendacja sampli — jak działa

`recommend_sample_for_instrument(instrument, lib, midi_layers)`:

1) zbiera wszystkie `note` z warstwy instrumentu
2) liczy medianę wysokości
3) wybiera sample, którego `root_midi` jest najbliżej mediany (o ile plik istnieje)

To jest mechanizm doradczy — renderer sam z siebie nie nadpisuje wyboru użytkownika.

## 7. Mini pipeline test

[mini_pipeline_test.py](mini_pipeline_test.py) pozwala uruchomić render bez frontendu:

- bierze istniejące `param_generation/output/<...>/parameter_plan.json`
- bierze istniejące `midi_generation/output/<...>/midi.json`
- opcjonalnie wczytuje `midi_per_instrument.json`
- składa `RenderRequest` i woła `render_audio()`

Uwaga: testowy pipeline może wstrzykiwać placeholder `selected_samples` jako `sample_id = instrument`, żeby nie blokować przepływu.
