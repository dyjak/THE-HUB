# AIR (backend) — dokumentacja modułów `app/air`

Ten dokument opisuje **bardzo szczegółowo** całą logikę backendu znajdującą się w `backend-fastapi/app/air`.

Moduł `air/` to „silnik” aplikacji do generowania muzyki, zorganizowany jako pipeline:

1. **`param_generation`** — planowanie wysokopoziomowych parametrów muzyki (meta, instrumenty, role) z pomocą LLM.
2. **`midi_generation`** — generowanie struktury MIDI (pattern/layers) z pomocą LLM + generacja artefaktów `.mid` i `pianoroll.svg`.
3. **`render`** — render audio na podstawie MIDI + wybranych sampli (inventory) → stem’y + mix.

Dodatkowo:

- **`providers`** — klienty i lista modeli dostawców AI (OpenAI/Anthropic/Gemini/OpenRouter).
- **`inventory`** — katalog sampli (single source of truth) oparty o `inventory.json`.
- **`export`** — manifest/ZIP do pobrania wszystkich artefaktów projektu.
- **`user_projects_router`** — lista projektów użytkownika (łącząca DB + pliki stanu renderu + param plan).
- **`gallery`** — proste portfolio (najmniej istotne).
- **`projects/store`** — prosty plikowy storage (aktualnie pomocniczy / przyszłościowy).

Szczegółowe opisy poszczególnych modułów są też w ich lokalnych README:

- `param_generation/README.md`
- `midi_generation/README.md`
- `render/README.md`
- `inventory/README.md`
- `providers/README.md`
- `export/README.md`
- `projects/README.md`
- `gallery/README.md`

> Ważne: w tym repo endpointy AIR są w praktyce „publiczne” na poziomie backendu (brak `Depends(get_current_user)`), a kontrola dostępu jest zakładana w warstwie frontendu (`/air/*`). W środowisku produkcyjnym warto to docelowo domknąć po stronie backendu.

---

## 0. Jak AIR jest wpięty do aplikacji (punkt wejścia)

Punktem wejścia backendu jest `backend-fastapi/app/main.py`.

W `main.py` dzieje się kilka kluczowych rzeczy:

1. **Ładowanie `.env` bardzo wcześnie** (żeby klucze API były dostępne zanim zaimportują się moduły providerów/AI).
2. **Rejestrowanie routerów** (w try/except — jeśli import modułu się wysypie, backend nadal wstanie, ale feature jest wyłączony z logiem ostrzeżenia).
3. **Mount statycznych katalogów output**:
   - `param_generation/output` pod `/api/param-generation/output/...`
   - `midi_generation/output` pod `/api/midi-generation/output/...`
   - `render/output` pod `/api/audio/...`
4. **Mount katalogu `local_samples/`** pod `/api/local-samples/...` (preview sampli po HTTP).

Z tego wynikają dwa „kanały IO”:

- **API**: JSON-y/endpointy sterujące pipeline.
- **Pliki**: outputy pipeline (JSON, wav, svg, mid) są publikowane jako statyczne zasoby.

---

## 1. Konwencje identyfikatorów i struktura outputów (klucz do zrozumienia pipeline)

W AIR istnieją dwa typy identyfikatorów:

### 1.1. `run_id` w `param_generation`

- `param_generation` generuje `run_id` tylko do debugowania (in-memory debug store).
- Realne outputy paramów są zapisywane w katalogu o nazwie:

```
param_generation/output/<UTC_YYYYMMDD_HHMMSS>_<run_id>/
  parameter_plan_raw.txt
  parameter_plan.json
```

- `run_id` jest sufiksem nazwy folderu, co umożliwia później szukanie folderu „po końcówce”.

### 1.2. `run_id` w `midi_generation` i `render`

- `midi_generation` (engine) generuje `run_id = uuid4().hex[:12]`.
- W projekcie przyjęto **konwencję, że stabilny identyfikator projektu to render run_id**, a w praktyce:

> `render_run_id` == `midi_run_id`

Zobacz komentarz w `midi_generation/router.py`:

- „Best-effort link: render_run_id == midi run_id in this app.”

Render output:

```
render/output/<run_id>/
  <project>_<instrument>_<timestamp>.wav   (stem)
  <project>_mix_<timestamp>.wav            (mix)
  render_state.json                        (request+response snapshot)
```

Uwaga praktyczna (ważne dla integracji frontendu): pola `mix_wav_rel` i `stems[].audio_rel` zwracane przez backend są obecnie tworzone jako ścieżki względne względem katalogu `air/render/` (czyli zwykle zawierają prefiks `output/` lub `output\` oraz systemowe separatory ścieżek). Ponieważ statyczny mount jest na `/api/audio` wskazujący bezpośrednio na `air/render/output/`, klient powinien:

- odciąć prefiks `output/` lub `output\\`
- znormalizować separatory do `/`

Finalnie URL ma postać: `/api/audio/<run_id>/<file>`.

MIDI output:

```
midi_generation/output/<UTC_YYYYMMDD_HHMMSS>_<run_id>/
  midi.json
  midi.mid                (opcjonalnie, jeśli jest mido)
  pianoroll.svg           (best-effort)
  midi_per_instrument.json (zbiorczy opis per-instrument; best-effort)
  midi_<instrument>.json
  midi_<instrument>.mid   (opcjonalnie)
  pianoroll_<instrument>.svg
```

### 1.3. Linkowanie kroku 1 (param) do kroku 3 (render)

Param i render mają różne run_id. Żeby eksport i lista projektów potrafiły skleić pipeline:

- `app/air/export/links.py` zapisuje mapowanie render_run_id → param_run_id w:

```
air/projects/output/step_links.json
```

To linkowanie jest „best-effort” (błędy linkowania nie mają zatrzymać pipeline).

---

## 2. Moduł `providers` (spojenie z API modeli AI)

### 2.1. Cel

`app/air/providers/client.py` jest warstwą adaptera do dostawców LLM.

- ładuje `.env` (z preferencją `backend-fastapi/.env`),
- udostępnia fabryki klientów:
  - `get_openai_client()` (OpenAI SDK, opcjonalnie `OPENAI_BASE_URL`),
  - `get_openrouter_client()` (OpenAI-compatible, `OPENROUTER_BASE_URL`),
  - `get_anthropic_client()`,
  - `get_gemini_client()`.

### 2.2. Konfiguracja przez env

Ważne zmienne środowiskowe:

- `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_MODELS` (opcjonalnie lista)
- `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, `ANTHROPIC_MODELS`
- `GOOGLE_API_KEY`, `GOOGLE_MODEL`, `GOOGLE_MODELS`
- `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `OPENROUTER_MODELS`, `OPENROUTER_BASE_URL`

`list_models(provider)`:

- dla OpenAI próbuje dynamicznie pobrać listę modeli i odfiltrować embedding/audio/tts/image,
- dla Gemini próbuje `g.list_models()` i filtruje modele obrazkowe heurystyką,
- dla Anthropic zwraca listę „kuratorowaną”,
- dla OpenRouter zwraca listę kuratorowaną lub override z env.

### 2.3. Endpointy z perspektywy UI

`param_generation` wystawia endpointy proxy do providerów:

- `GET /api/air/param-generation/providers`
- `GET /api/air/param-generation/models/{provider}`

Frontend dzięki temu ma „source of truth” co można wybrać.

---

## 3. Moduł `inventory` (składowanie i ładowanie sampli)

### 3.1. Filozofia

`inventory` jest single source of truth dla sampli.

- runtime moduły (`render`, `param_generation`) mają się opierać o `inventory.json`,
- `inventory.json` można przebudować automatycznie skanem katalogu `local_samples/`.

### 3.2. Gdzie są sample

`inventory.py` zakłada domyślny root:

- `DEFAULT_LOCAL_SAMPLES_ROOT = <repo_root>/local_samples`

Backend montuje ten katalog statycznie:

- `/api/local-samples/<path>`

### 3.3. Struktura pliku `inventory.json`

Generowany `inventory.json` (`app/air/inventory/inventory.json`) ma m.in. pola:

- `schema_version`: `air-inventory-1`
- `generated_at`: timestamp
- `root`: ścieżka roota sampli (zwykle absolute)
- `instrument_count`, `total_files`, `total_bytes`
- `instruments`: map `{instrument: {count, examples[]}}`
- `samples`: lista rekordów (jeden rekord = jeden plik audio)

Każdy rekord sample (`row`) ma typowo:

- `instrument`: nazwa instrumentu (np. `Kick`, `Piano`, `Pads`, `FX`)
- `id`: stabilne ID (tutaj: `file_rel` w formacie posix)
- `file_rel`: path względem `root`
- `file_abs`: absolutna ścieżka
- `bytes`, `source`, `pitch`, `category`, `family`, `subtype`
- (deep-mode) `sample_rate`, `length_sec`, `loudness_rms`, `gain_db_normalize`, `root_midi`

Kluczowa decyzja: **ID sample to `rel.as_posix()`**, czyli stabilne i łatwe do debugowania.

### 3.4. Budowa inventory: `build_inventory(deep=False)`

`build_inventory`:

1. Rekurencyjnie skanuje `local_samples/**/*` po rozszerzeniach audio.
2. Pomija pliki z nazwą zawierającą `downlifter` lub `uplifter`.
3. Dla WAV robi szybki check integralności (próba otwarcia `wave.open`).
4. Klasyfikuje plik na instrumenty przez heurystykę `classify()`:
   - tokenizacja ścieżki i nazwy pliku,
   - reguły „specjalne” dla nazw zawierających konkretne frazy,
   - reguły folderowe (`FX`, `Pads`, `Strings`, `Piano`, `Instruments/Guitar/...` itd.),
   - klasyfikacja perkusji do kategorii `Drums` z subtype,
   - fallback do `Pads` albo `FX` zależnie od folderu.
5. (opcjonalnie `deep=True`) liczy metadane:
   - RMS i sugerowany gain do normalizacji (target ~0.2),
   - długość i sample rate,
   - estimate pitch FFT (`estimate_root_pitch`) → `root_midi`.
6. Składa payload i zapisuje do `inventory.json`.

**Dlaczego `deep` jest opcjonalne?**

- analizowanie RMS i FFT bywa kosztowne na dużych bibliotekach,
- pipeline renderu działa bez `deep`, ale z `deep` ma dodatkowe benefity:
  - normalizacja głośności (`gain_db_normalize`),
  - trafniejsze dobieranie sampli (`root_midi`).

### 3.5. Runtime API dla innych modułów

#### 3.5.1. Cache: `app/air/inventory/access.py`

- `get_inventory_cached(deep=False)` jest `@lru_cache(maxsize=1)` i robi:
  - `load_inventory()`;
  - jeśli brak pliku → `build_inventory()`.

- `ensure_inventory(deep=False)` wymusza rebuild i czyści cache.

#### 3.5.2. Runtime map instrument → sample

`app/air/inventory/local_library.py`:

- `discover_samples()` wczytuje `inventory.json` i buduje mapę:

`{ instrument_name: [LocalSample, ...] }`

`LocalSample` to dataclass zawierający m.in. `file: Path`, `id`, `root_midi`, `gain_db_normalize`.

To jest dokładnie to, czego używa `render.engine`.

### 3.6. HTTP API inventory

Router: `app/air/inventory/router.py` prefiks `/air/inventory`.

- `GET /api/air/inventory/meta`
- `GET /api/air/inventory/available-instruments`
- `GET /api/air/inventory/inventory`
- `POST /api/air/inventory/rebuild?mode=deep|...`
- `GET /api/air/inventory/samples/{instrument}?offset&limit`
- `POST /api/air/inventory/select` — prosta deterministyczna selekcja (offset modulo)

Ważne: inventory buduje też `url` dla preview:

- `/api/local-samples/<file_rel>`

---

## 4. Moduł `param_generation` (krok 1 pipeline)

### 4.1. Cel

`param_generation` generuje **plan parametrów muzycznych**, nie nut.

Wyjściem ma być JSON:

```json
{"meta":{...}}
```

z informacjami typu: tempo, tonacja, metrum, długość, instrumenty, role instrumentów.

### 4.2. Struktury danych

`app/air/param_generation/schemas.py`:

- `ParameterPlanIn`: wejściowe parametry (częściowo defaulty), zawiera `prompt`.
- Walidatory:
  - normalizacja `instruments` (lista, filtr do dozwolonych),
  - automatyczne `instrument_configs` jeśli brak.

Istotny mechanizm: `INSTRUMENT_OPTIONS` może zostać **dynamicznie rozszerzony** o instrumenty z inventory (`list_instruments()`), aby UI i LLM mogły pracować z aktualnym katalogiem.

### 4.3. Endpointy

Router: `app/air/param_generation/router.py` prefiks `/air/param-generation`.

1) Dostawcy i modele:

- `GET /api/air/param-generation/providers`
- `GET /api/air/param-generation/models/{provider}`

2) Proxy do inventory:

- `GET /api/air/param-generation/available-instruments`
- `GET /api/air/param-generation/samples/{instrument}?offset&limit`

Ten proxy jest ważny, bo UI kroku 1/parametrów nie musi wiedzieć o osobnym module inventory — ma wszystko „w jednym prefiksie”.

3) Generowanie planu:

- `POST /api/air/param-generation/plan`

4) Debug + odtwarzanie stanu:

- `GET /api/air/param-generation/debug/{run_id}` (in-memory debug log)
- `GET /api/air/param-generation/plan/{run_id}` (wczytanie `parameter_plan.json` z dysku)

Uwaga implementacyjna (ważne dla „odporności” UX): odczyt `parameter_plan.json` z dysku jest bardziej defensywny niż sam parser odpowiedzi modelu. Jeśli plik JSON ma doklejone śmieci albo jest lekko uszkodzony, backend próbuje znaleźć **najdłuższy poprawny prefiks JSON** (od pierwszej `{` do jakiejś końcowej pozycji), zamiast polegać wyłącznie na „ostatniej klamrze”. Ta sama strategia jest używana w endpointach `PATCH`, żeby nie blokować edycji planu.

5) Aktualizacje planu przez frontend:

- `PATCH /api/air/param-generation/plan/{run_id}/selected-samples`
- `PATCH /api/air/param-generation/plan/{run_id}/meta`

### 4.4. Jak powstaje prompt do LLM

Funkcja `_parameter_plan_system(plan)` buduje:

- **system prompt**: bardzo restrykcyjny opis roli modelu + schema JSON + constraints.
- **user payload**: minified JSON `{task, user_prompt}`.

Istotne elementy constraints:

- lista dozwolonych instrumentów jest wstrzykiwana do prompta (preferencyjnie z inventory),
- wymóg spójności `instruments` i `instrument_configs` (identyczne nazwy, identyczna liczba),
- normalizacja po stronie backendu w `schemas.py` również filtruje instrumenty.

### 4.5. Wywołanie modeli

`_call_model(provider, model, system, user)`:

- OpenAI: `chat.completions.create(temperature=0.0)`
- Anthropic: `messages.create(max_tokens=2048, temperature=0.0)`
- Gemini: `GenerativeModel.generate_content(user)` + kilka fallbacków do ekstrakcji tekstu
- OpenRouter: OpenAI-compatible

Temperatura w tym module jest 0.0 → preferencja na deterministyczny JSON.

### 4.6. Parsowanie i odporność na błędy

`_safe_parse_json(raw)`:

- usuwa potencjalne ``` fences,
- w razie błędu próbuje „przyciąć” do ostatniej klamry `}`,
- zbiera listę `errors` (nie tylko jeden błąd).

To jest krytyczne dla UX: nawet jeśli model „doklei śmieci” na końcu, pipeline nie zawsze musi się zatrzymać.

### 4.7. Zapisywanie outputu

`POST /plan` zapisuje do folderu `OUTPUT_DIR/<timestamp>_<run_id>/`:

- `parameter_plan_raw.txt` (raw output modelu)
- `parameter_plan.json` (zparsowany JSON jeśli udało się)

Dodatkowo do `parsed` dopina się `user_prompt` jako top-level, żeby późniejsze PATCH-e `meta` nie nadpisały oryginalnego prompta.

### 4.8. Proxy: dopasowanie instrumentów do inventory

`GET /samples/{instrument}` jest bardziej zaawansowany niż inventory:

- rozumie agregatory (`drums`/`drumkit` → wszystkie drum parts z kategorii Drums),
- rozumie agregator `fx` → wszystkie instrumenty z kategorii FX,
- posiada `_resolve_target_instruments()` z synonimami i heurystyką.

Dzięki temu UI może pytać o „Drums” i dostać sensowną listę.

---

## 5. Moduł `midi_generation` (krok 2 pipeline)

### 5.1. Cel

Wygenerować strukturę MIDI na siatce 8-stepów na takt:

- `pattern`: lista bar → events (typowo perkusja)
- `layers`: obiekt instrument → lista bar → events (melodia/harmonia)
- `meta`: wypełnione z param_generation (tempo, bars, instruments...)

### 5.2. Kontrakt danych

`app/air/midi_generation/schemas.py`:

- `MidiMetaIn` to minimalny podzbiór meta (tempo/key/scale/bars/instruments + instrument_configs).
- `MidiGenerationIn`:
  - `meta` (wymagane)
  - `provider`, `model` (opcjonalne)
  - `param_run_id` (opcjonalny, tylko do linkowania eksportu)
  - `ai_midi` (opcjonalne: ręcznie wstrzyknięty JSON do debug)

Wyjście `MidiGenerationOut` zawiera:

- `run_id`
- `midi` (globalny)
- `artifacts` (ścieżki rel do output folder)
- `midi_per_instrument` + `artifacts_per_instrument`
- oraz (jeśli AI) `system/user/raw/parsed/errors`.

### 5.3. Endpointy

Router: `app/air/midi_generation/router.py` prefiks `/air/midi-generation`.

- `POST /api/air/midi-generation/compose`
- `GET /api/air/midi-generation/run/{run_id}`

### 5.4. Prompt do LLM (kompozytor)

`_call_composer()` buduje system prompt z mocnymi constraintami:

- „MUST NOT skip any instrument listed in meta.instruments”
- siatka 8 kroków na takt
- mapowanie GM dla perkusji
- teoria: nuty w skali `key scale`

Temperatura = 0.2 (trochę kreatywności, ale nadal JSON).

### 5.5. Parsowanie outputu AI

`engine._safe_parse_midi_json`:

- analogicznie do param: usuwa fences, przycina do ostatniej klamry.

Dodatkowo engine robi `_ensure_midi_structure(meta, midi_data)`:

- dopina brakujące pola `meta` z paramów,
- jeśli brak `layers` → tworzy pusty dict,
- jeśli brak `pattern` → buduje pattern jako suma eventów z layers.

To powoduje, że downstream `render` ma prawie zawsze to, czego potrzebuje.

### 5.6. Generacja artefaktów

`generate_midi_and_artifacts(meta, midi_data)`:

1. Generuje `run_id` i katalog `output/<timestamp>_<run_id>`.
2. Zapisuje `midi.json`.
3. Best-effort eksport `.mid` (jeżeli jest `mido`).
4. Best-effort render `pianoroll.svg`.
5. Dzieli MIDI per instrument:
   - dla melodii bierze `layers[inst]` → pattern zbudowany z warstwy,
   - dla perkusji, jeśli instrument nie ma warstwy, filtruje globalny `pattern` po nutach GM.
6. Zapisuje `midi_<inst>.json` oraz opcjonalne `.mid` i `pianoroll_<inst>.svg`.

Dodatkowo (best-effort) zapisuje też jeden plik zbiorczy `midi_per_instrument.json`, który zawiera mapę `{instrument -> midi_object}` i jest wykorzystywany m.in. przez narzędzia developerskie (np. `render/mini_pipeline_test.py`).

### 5.7. Link do param_run_id

W `router.compose()`:

- jeśli request miał `param_run_id`, to zapisywany jest link przez `export.links.link_param_to_render(run_id, param_run_id)`.

Ta informacja jest potem wykorzystywana przez `export` i `user_projects_router`.

---

## 6. Moduł `render` (krok 3 pipeline)

### 6.1. Cel

Zamienić plan MIDI + wybór sampli na audio:

- stem’y per instrument (stereo wav)
- finalny mix (stereo wav)

### 6.2. Kontrakt danych

`app/air/render/schemas.py`:

`RenderRequest`:

- `project_name` (nazwa, używana w nazwach plików)
- `run_id` (klucz folderu output)
- `user_id` (opcjonalny, do DB)
- `midi` (globalne midi.json)
- `midi_per_instrument` (opcjonalne, preferowane jeśli jest)
- `tracks`: lista `TrackSettings` (instrument, enabled, volume_db, pan)
- `selected_samples`: map instrument → sample_id (ID z inventory)
- `fadeout_seconds`: kontrola „voice stealing”

`RenderResponse`:

- `mix_wav_rel` (ścieżka zwracana przez backend; patrz uwaga o prefiksie `output/` powyżej)
- `stems`: lista `{instrument, audio_rel}`
- `sample_rate`, `duration_seconds`

### 6.3. Endpointy

Router: `app/air/render/router.py` prefiks `/air/render`.

- `POST /api/air/render/render-audio`
- `GET /api/air/render/run/{run_id}`
- `POST /api/air/render/recommend-samples`

### 6.4. Render: źródła danych

`render.engine` używa:

- `inventory.local_library.discover_samples()` → mapa instrument → LocalSample.
- `_resolve_sample_for_instrument()`:
  1) jeśli `selected_samples[instrument]` jest podane → szukaj po ID,
  2) fallback: pierwszy istniejący sample.

To jest świadoma decyzja: renderer nie ma „magicznie” zmieniać wyboru użytkownika.

### 6.5. Rekomendacja sampli (doradcza)

`recommend_sample_for_instrument()`:

- zbiera wszystkie `note` z MIDI warstwy instrumentu,
- liczy medianę,
- wybiera sample z `root_midi` najbliższym medianie.

`POST /recommend-samples`:

- iteruje po `tracks` i zwraca mapę instrument → polecany sample.
- niczego nie zapisuje.

### 6.6. Silnik renderu: algorytm

Poniżej mechanika `render_audio(req)`:

1) **Ustalenie długości utworu**

- preferuje `meta.bars` i `meta.length_seconds`,
- fallback: wylicza max bar z `pattern` i `layers`,
- kroki: `total_steps = bars * 8`.

2) **Ustalenie rozdzielczości osi czasu**

- `frames = sr * duration_sec`,
- `step_samples_global = frames / total_steps`.

3) **Dla każdego tracka** (`TrackSettings`)

- pobierz sample (wav) i wczytaj mono (`_read_wav_mono`):
  - preferuje `scipy.io.wavfile`, fallback `wave` (16-bit).

Ważne ograniczenie: renderer działa na stałym `sr = 44100` i **ignoruje sample-rate z pliku WAV**. Jeśli sample nie mają 44100 Hz, odtwarzanie będzie miało błędny pitch/tempo.
- jeśli sample ma `gain_db_normalize`, przeskaluj amplitudę.

4) **Złożenie mono bufora instrumentu**

- `buf = [0]*frames`
- wybór warstwy MIDI:
  - jeśli `midi_per_instrument[instrument]` istnieje, to preferuje `pattern` tej instancji (perkusja), inaczej `layers[instrument]`,
  - fallback: global `midi.layers[instrument]`.

Dodatkowy detal implementacyjny: renderer usuwa historyczny problem „ciszy na początku”, gdy generator MIDI numeruje takty od `1`. Jeśli minimalny `bar` w wybranej warstwie wynosi dokładnie `1`, renderer odejmuje przesunięcie `min_bar=1` (bez agresywnego przesuwania bardziej nietypowych indeksów).

5) **Voice stealing (fade-out ogona)**

Jeśli nowy event startuje zanim poprzedni skończył:

- wygasza krótko fragment ogona (liniowo) przez `fadeout_seconds`,
- resztę ogona czyści do zera.

Cel: uniknięcie „kliku” i nadmiernego nakładania ogonów.

6) **Pitch shifting (melodiczne instrumenty)**

- perkusja (`perc_set`) → zawsze raw sample, bez pitchowania.
- instrumenty melodyczne:
  - jeśli `sample.root_midi` jest znane, to `base_midi` = round(root_midi),
  - liczy różnicę `raw_semi = target_midi - base_midi`,
  - kompresuje różnicę przez `tanh(raw_semi/max_semi) * max_semi`,
  - z tego wylicza ratio i robi resampling.

`max_semi` jest dobierane per instrument (żeby ograniczyć nienaturalne transpozycje):

- `bass`, `bass guitar` → 7 półtonów
- `piano`, `pads`, `strings`, `sax`, `acoustic guitar`, `electric guitar` → 24 półtony
- pozostałe instrumenty melodyczne → 18 półtonów

To jest ważna decyzja „muzyczna”:

- małe interwały są prawie liniowe (zgodne z MIDI),
- duże interwały są kompresowane (żeby sample nie odlatuje o kilka oktaw).

7) **Envelope**

- attack 0.01s
- release 0.1s

Uwaga: renderer **nie używa pola `len`** z eventu MIDI do sterowania długością nuty. Długość wynika z długości sampla po pitch-shifcie oraz z voice stealing (kolejny event może wyciąć ogon poprzedniego).

8) **Pan/volume i zapis stemu**

- `gain = db_to_gain(volume_db)`
- `pan_gains(pan)` constant-power
- zapis stereo wav przez `_write_wav_stereo`.

9) **Mix**

- sumuje lewy i prawy kanał stemów (`_mix_tracks`),
- robi prostą normalizację do 0.9 peak,
- zapisuje `*_mix_*.wav`.

Praktyczny detal: normalizacja jest wykonywana przez `_mix_tracks()` osobno dla lewego i prawego kanału (czyli każdy kanał jest skalowany niezależnie). To może minimalnie zmienić obraz stereo w zależności od zawartości kanałów.

10) **Błąd, jeśli nic nie wyrenderowano**

Jeśli żaden instrument nie dał stemu:

- rzuca `RuntimeError({error:"render_no_instruments", ...})`

Router łapie i zwraca HTTP 500 z detalami.

### 6.7. Zapisy stanu i DB

`render/router.py` po udanym renderze robi „best-effort”:

- zapis rekordu `Proj(user_id, render=run_id)` do DB,
- zapis `render_state.json` w `render/output/<run_id>/`:

```json
{
  "request": {... RenderRequest ...},
  "response": {... RenderResponse ...}
}
```

To jest krytyczne, bo `user_projects_router` bazuje na `render_state.json`.

---

## 7. Moduł `export` (pobieranie zasobów)

### 7.1. Cel

Dać frontendowi możliwość pobrania wszystkich artefaktów projektu jako:

- manifest listy plików (z URL)
- jeden ZIP

### 7.2. Kontrakt

Router: `app/air/export/router.py` prefiks `/air/export`.

- `GET /api/air/export/list/{render_run_id}` (opcjonalnie query: `param_run_id`)
- `GET /api/air/export/zip/{render_run_id}` (opcjonalnie query: `param_run_id`)

`ExportManifest` zawiera:

- `render_run_id`
- `midi_run_id` (zwykle to samo)
- `param_run_id` (jeśli udało się znaleźć)
- `files[]`: {step, rel_path, url, bytes}
- `missing[]`: lista brakujących kroków

### 7.3. Jak export znajduje pliki

`collector.py`:

- render: `render/output/<render_run_id>/...` (autorytatywne)
- midi: szuka folderu `midi_generation/output/*_<run_id>`
- param: szuka folderu `param_generation/output/*_<param_run_id>`

Param run id bierze:

- z query `param_run_id`,
- albo z linku `get_param_for_render(render_run_id)`.

### 7.4. ZIP

ZIP jest budowany do `SpooledTemporaryFile` i streamowany.

Mechanizmy bezpieczeństwa:

- arcname jest normalizowany (`..` i puste segmenty wycinane),
- duplikaty arcnames dostają suffix `__N`.

---

## 8. Moduł `user_projects_router` (projekty użytkownika)

### 8.1. Cel

Frontend potrzebuje listy projektów użytkownika:

- podstawowe metadane,
- ścieżki do renderów,
- prompt i meta parametrów,
- informacja jakie sample były wybrane.

### 8.2. Endpointy

Router: `app/air/user_projects_router.py` prefiks `/air/user-projects`.

- `GET /api/air/user-projects/by-user?user_id=...&limit=...`
- `PATCH /api/air/user-projects/rename?project_id=...&name=...`
- `DELETE /api/air/user-projects/delete?project_id=...`

### 8.3. Skąd biorą się dane

`/by-user`:

1) Z DB pobiera rekordy `Proj` dla `user_id` (sort po `created_at desc`).
2) Dla każdego rekordu bierze `run_id = Proj.render`.
3) Wczytuje `render_state.json` i buduje `RenderResponse`.
4) Próbuje wzbogacić:
   - `param_run_id` z `step_links.json` (`get_param_for_render`),
   - wczytuje `parameter_plan.json` i wyciąga `prompt` + `param_meta`.
5) Jeśli linku brak, próbuje inferować plan param po `selected_samples`:
   - iteruje po param outputach i porównuje `meta.selected_samples`.
6) Rozwiązuje `selected_samples_info` przez inventory:
   - mapuje sample_id → `{name,url,pitch,subtype,family,category}`.

To jest ważne: lista projektów jest „sklejona” z wielu źródeł (DB + render files + param files + inventory).

### 8.4. Rename

`/rename`:

- nie ma „name” w DB, więc zmienia `response.project_name` w `render_state.json`.

### 8.5. Delete

`/delete`:

- usuwa tylko rekord DB,
- **nie usuwa plików renderu**.

---

## 9. Moduł `gallery` (portfolio)

`gallery/router.py` to prosta lista statycznych placeholderów (SoundCloud URLs).

- `GET /api/air/gallery/meta`
- `GET /api/air/gallery/items`

To jest najmniej istotne dla pipeline.

---

## 10. Moduł `projects/store` (plikowy store)

`projects/store.py` zapewnia prosty plikowy zapis pod:

```
air/projects/output/<project_id>.json
```

W tym samym katalogu (obok plików projektów) trzymane jest też mapowanie kroków pipeline:

```
air/projects/output/step_links.json
```

Plik jest zapisywany przez `export/links.py` i służy do linkowania `render_run_id -> param_run_id` (best-effort).

Funkcje:

- `load_project(project_id)`
- `save_project(project_id, data)` (merge z istniejącym)

W aktualnym kodzie AIR główny flow projektów jest oparty o DB `Proj` + pliki renderu, ale ten store może być użyty jako rozszerzenie (np. pełny snapshot pipeline, settings UI, itd.).

---

## 11. Mini pipeline test (narzędzie developerskie)

`render/mini_pipeline_test.py` to ręczny skrypt CLI pozwalający:

- wziąć istniejące outputy z `param_generation/output` i `midi_generation/output`,
- zbudować `RenderRequest`,
- odpalić `render_audio()`.

Ważne: skrypt sztucznie dopina `meta.selected_samples` jako placeholder (`sample_id = instrument`), więc jest to narzędzie demonstracyjne — nie zastępuje prawdziwego flow UI.

---

## 12. Przykładowy pełny przebieg pipeline (end-to-end)

Poniżej „idealny” flow frontendu:

### 12.1. Krok 1 — param plan

1) Front pyta o modele:

- `GET /api/air/param-generation/providers`
- `GET /api/air/param-generation/models/gemini`

2) Front wysyła prompt:

- `POST /api/air/param-generation/plan`

3) Odpowiedź zawiera `parsed.meta`.

4) Front pozwala edytować meta i wybiera sample z inventory (przez proxy):

- `GET /api/air/param-generation/samples/Piano`
- `PATCH /api/air/param-generation/plan/{param_run_id}/selected-samples`
- `PATCH /api/air/param-generation/plan/{param_run_id}/meta`

### 12.2. Krok 2 — MIDI

- `POST /api/air/midi-generation/compose` z:
  - `meta = parsed.meta` (wraz z instrumentami),
  - `param_run_id = <param_run_id>`.

Odpowiedź daje `run_id` oraz `midi` + per instrument.

### 12.3. Krok 3 — render

- `POST /api/air/render/render-audio`

`run_id` w render request powinien być tym samym co z MIDI (żeby eksport działał po jednym ID projektu).

Render zapisuje pliki w `/api/audio/<run_id>/...` oraz `render_state.json`.

### 12.4. Eksport

- `GET /api/air/export/list/{render_run_id}`
- `GET /api/air/export/zip/{render_run_id}`

---

## 13. Błędy i edge-case’y (ważne dla UX)

### 13.1. `param_generation`

- 422: walidacja `ParameterPlanIn` nie przeszła.
- 400: błąd provider’a (`unknown_provider`, brak klucza API).
- parse errors: model zwrócił nie-JSON → `parsed` może być null + `errors`.

### 13.2. `midi_generation`

- jeśli AI zwróci zły JSON, parser oddaje `{}` + errors, a engine uzupełnia strukturę.
- `.mid` może nie powstać jeśli `mido` nie jest zainstalowane.

### 13.3. `render`

- brak `selected_samples` → renderer bierze pierwszy sample.
- brak sampli dla instrumentu → instrument pomijany.
- jeśli wszystkie instrumenty wypadną → `render_no_instruments` (500).

### 13.4. `inventory`

- brak `local_samples/` → inventory może być puste.
- uszkodzone wav → plik nie trafia do inventory.

---

## 14. Wskazówki i TODO (z `app/air/TODO.md`)

W repo jest lista tematów do dopracowania. Najważniejsze w kontekście jakości generacji:

- normalizacja głośności instrumentów w renderze (częściowo już jest: `gain_db_normalize`),
- lepsze ostrzeżenia dla użytkownika gdy AI zwróci złą odpowiedź,
- dokumentacja promptów (ten plik jest krokiem w tę stronę),
- aktualizacja list modeli AI i informacja o wydajności przy wielu instrumentach,
- klarowne błędy gdy brakuje sampli / MIDI jest niepoprawne.

---

## 15. Szybka mapa plików (co jest gdzie)

- `air/param_generation/router.py` — endpointy planowania + proxy do inventory
- `air/param_generation/schemas.py` — walidacja i normalizacja inputu
- `air/param_generation/debug_store.py` — debug log in-memory

- `air/providers/client.py` — dostawcy AI, klucze, listy modeli

- `air/midi_generation/router.py` — endpointy MIDI
- `air/midi_generation/engine.py` — zapis artefaktów i podział per instrument
- `air/midi_generation/schemas.py` — modele wejścia/wyjścia

- `air/render/router.py` — endpoint renderu + zapis state + DB
- `air/render/engine.py` — silnik audio
- `air/render/schemas.py` — modele wejścia/wyjścia

- `air/inventory/inventory.py` — budowa inventory.json
- `air/inventory/access.py` — cache/rebuild
- `air/inventory/router.py` — endpointy katalogu
- `air/inventory/local_library.py` — runtime LocalSample map
- `air/inventory/analyze_pitch_fft.py` — analiza pitch (deep)

- `air/export/router.py` — manifest/zip
- `air/export/collector.py` — skan folderów
- `air/export/links.py` — step_links.json (render → param)

- `air/user_projects_router.py` — lista projektów użytkownika
- `air/projects/store.py` — prosty file store

- `air/gallery/router.py` — portfolio

