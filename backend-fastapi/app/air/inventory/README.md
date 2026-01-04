# AIR (backend) — `inventory`

Ten moduł jest **single-source-of-truth** dla katalogu sampli audio dostępnych lokalnie w repo, w katalogu `local_samples/`.

W skrócie:

- `inventory.py` skanuje `local_samples/` i buduje `inventory.json` (opcjonalnie w trybie „deep”).
- `access.py` trzyma `inventory.json` w prostym cache w pamięci (żeby inne moduły nie czytały pliku w kółko).
- `router.py` udostępnia endpointy dla UI: lista instrumentów, sample dla instrumentu, przebudowa katalogu, szybki dobór “pierwszych” sampli.

Renderer audio i kroki AI (param/midi/render) **nie powinny skanować filesystemu**. W runtime wszystkie listy instrumentów / metadane sampli mają pochodzić z `inventory.json`.

## 1. Pliki w module

- `inventory.json` — wygenerowany katalog (kanoniczny artefakt).
- `inventory.py` — builder: skan `local_samples/`, klasyfikacja, zapis `inventory.json`.
- `access.py` — runtime cache + helpery (`get_inventory_cached`, `ensure_inventory`, `list_instruments`).
- `local_library.py` — “biblioteka runtime” dla innych modułów (mapa instrument → `LocalSample`, lookup po id).
- `router.py` — API HTTP pod `/api/air/inventory/*`.
- `analyze_pitch_fft.py` — pomocnicza analiza `root_midi` (FFT) używana w trybie `deep=True`.

## 2. Statyczny mount sampli (odsłuch)

Backend wystawia katalog `local_samples/` statycznie pod:

- `/api/local-samples/<file_rel>`

To jest montowane w `main.py` przez `StaticFiles(directory=.../local_samples)`.

Konsekwencje:

- URL do odsłuchu budujemy z `file_rel` (POSIX, z `/`).
- W praktyce `file_rel` z `inventory.json` powinno być ścieżką względną względem `local_samples/`.

## 3. API HTTP (FastAPI)

Prefiks routera: `/api/air/inventory`

### 3.1. `GET /meta`

Zwraca proste informacje diagnostyczne: `schema_version` oraz listę podstawowych endpointów.

Uwaga: lista w `meta.endpoints` nie jest traktowana jako „pełna specyfikacja” (np. endpoint `/select` nie jest tam wymieniony).

### 3.2. `GET /available-instruments`

Zwraca posortowaną listę instrumentów dostępnych w katalogu oraz liczbę instrumentów.

Źródło: `access.get_inventory_cached()` → `inv["instruments"].keys()`.

### 3.3. `GET /inventory`

Zwraca pełne `inventory.json`.

Zachowanie:

- próbuje `load_inventory()`
- jeśli pliku nie ma albo jest nieczytelny → robi `build_inventory()` i zwraca wynik

Istotny szczegół integracyjny: endpoint `/inventory` **nie czyści cache** z `access.get_inventory_cached()`.
Jeśli ktoś podmieni `inventory.json` na dysku w trakcie działania serwera, to endpointy oparte o cache (`/samples`, `/available-instruments`, `/select`) mogą zwracać stare dane aż do restartu lub `/rebuild`.

### 3.4. `POST /rebuild?mode=deep`

Wymusza przebudowę katalogu i czyści cache w pamięci.

- `mode` jest parametrem query (`mode=deep` włącza wolniejszy wariant analizy)
- bez `mode` działa wariant szybki (`deep=False`)

Po rebuildzie serwer:

1) zapisuje nowe `inventory.json`
2) `cache_clear()`
3) dogrzewa cache pojedynczym `get_inventory_cached()`

### 3.5. `GET /samples/{instrument}?offset=0&limit=100`

Zwraca listę sampli dla konkretnego instrumentu (paginacja) + “default” (pierwszy element listy).

Parametry:

- `offset` — start
- `limit` — liczba elementów (zabezpieczenie: limit jest clampowany do max 500)

Response ma uproszczony format do UI (m.in. `url` do odsłuchu):

```json
{
  "instrument": "Kick",
  "count": 32,
  "offset": 0,
  "limit": 100,
  "default": { "id": "Drums/.../kick.wav", "url": "/api/local-samples/Drums/.../kick.wav", "name": "kick.wav" },
  "items": [ ... ]
}
```

Budowanie URL (logika z `router.py`):

```python
rel_posix = Path(file_rel).as_posix()
url = "/api/local-samples/" + quote(rel_posix, safe="/")
```

### 3.6. `POST /select`

Prosty, deterministyczny endpoint “wybierz po jednym samplu na instrument”, bez AI.

Wejście:

```json
{ "instruments": ["Kick", "Snare"], "offset": 0 }
```

Wyjście:

```json
{
  "selections": [
    {"instrument":"Kick","id":"...","url":"/api/local-samples/...","name":"..."}
  ],
  "missing": null
}
```

Zachowanie:

- dla każdego instrumentu bierze listę sampli z `inventory.samples`
- wybiera `inst_rows[offset % len(inst_rows)]`
- `offset` pozwala “przewijać” wybór

## 4. `inventory.json` — schemat i znaczenie pól

`inventory.json` jest zapisywany w tym folderze: `app/air/inventory/inventory.json`.

Najważniejsze pola top-level:

- `schema_version`: zawsze `air-inventory-1`
- `generated_at`: timestamp (float)
- `root`: string (zwykle absolutna ścieżka do `local_samples/`)
- `deep`: bool (czy użyto trybu deep)
- `instrument_count`, `total_files`, `total_bytes`: statystyki
- `instruments`: mapowanie instrument → `{count, examples[]}`
- `samples`: lista rekordów sampli

Najważniejsze pola w `samples[]`:

- `instrument`: nazwa instrumentu (np. `Kick`, `FX`, `Piano`)
- `id`: stabilny identyfikator = `file_rel` (POSIX), np. `Drums/HipHop/Kick.wav`
- `file_rel`: ścieżka względna względem `local_samples/` (POSIX)
- `file_abs`: absolutna ścieżka na dysku
- `bytes`: rozmiar pliku
- `source`: zwykle `local`
- `pitch`: próba wyciągnięcia tonu z nazwy pliku (np. `C#4`), jeśli wykryto
- `category`, `family`, `subtype`: metadane z klasyfikacji

Pola “deep” (jeśli `deep=True`):

- `sample_rate`, `length_sec`: czytane z WAV (dla innych formatów zwykle `null`)
- `loudness_rms`: RMS policzone na max 60 s materiału
- `gain_db_normalize`: propozycja gain w dB do przybliżonego RMS≈0.2
- `root_midi`: oszacowanie tonu (FFT) jako wartość MIDI (float)

## 5. Budowanie inventory — skan, filtr, klasyfikacja

Builder jest w `build_inventory(deep: bool)`.

### 5.1. Co jest skanowane

- skan: `DEFAULT_LOCAL_SAMPLES_ROOT.rglob("*")`
- wspierane rozszerzenia: `{.wav, .mp3, .aif, .aiff, .flac, .ogg, .m4a, .wvp}`
- filtr: pomijane nazwy plików zawierające `downlifter` lub `uplifter`

### 5.2. Szybki test poprawności plików

W trakcie skanu builder próbuje otworzyć `.wav` przez `wave.open()` i jeśli to się nie uda, plik nie trafia do katalogu.
Inne formaty są obecnie traktowane jako “zaufane” (brak walidacji).

### 5.3. Klasyfikacja instrumentu

Klasyfikacja jest heurystyczna i odporna:

- tokenizuje ścieżkę + nazwę pliku (lowercase)
- dodaje dodatkowe tokeny jeśli słowa kluczowe są substringami (np. `clubkick` → `kick`)
- rozpoznaje kilka “hard-coded” wyjątków (np. `ACOUSTICG` → Acoustic Guitar)
- rozpoznaje typowe układy folderów (`Drums/...`, `Instruments/...`)
- perkusję mapuje do instrumentów typu `Kick`, `Snare`, `Hat`, itd.

### 5.4. Tryb `deep=True`

Tryb deep jest wolniejszy i ma sens głównie dla `.wav`:

- czyta WAV i liczy RMS (maksymalnie 60 sekund)
- proponuje `gain_db_normalize`, żeby RMS sampla był w okolicach 0.2
- próbuje wyznaczyć `root_midi` metodą FFT (`estimate_root_pitch`)

Wymagania środowiskowe:

- analiza FFT wymaga `numpy` (moduł `analyze_pitch_fft.py` importuje `numpy` na poziomie modułu).

## 6. Runtime: cache i `local_library`

### 6.1. Cache (`access.py`)

`get_inventory_cached()` jest opakowane w `@lru_cache(maxsize=1)`.

Konsekwencje:

- odczyt jest szybki
- ale jeśli zmienisz `inventory.json` ręcznie, proces nie zobaczy zmian bez `cache_clear` (czyli `/rebuild`) lub restartu

### 6.2. `local_library.py`

`discover_samples(deep=False)` buduje mapę instrument → lista `LocalSample` **wyłącznie z `inventory.json`**.

Ważna uwaga: argument `deep` jest tam ignorowany (zakładamy, że deep informacje są już zapisane w JSON).
