# AIR (backend) — `export`

Ten moduł umożliwia **eksport artefaktów projektu** (param → midi → render) w dwóch formach:

- manifest JSON z listą plików do pobrania,
- ZIP ze wszystkimi znalezionymi plikami.

Najważniejsze założenia z kodu:

- stabilnym identyfikatorem projektu jest `render_run_id`,
- output renderu jest traktowany jako **źródło prawdy**,
- pliki z `midi_generation` i `param_generation` są dołączane **best-effort** (mogą nie istnieć),
- moduł nie zmienia struktur outputów — tylko je skanuje.

## 1. Pliki w module

- [router.py](router.py) — endpointy: manifest i zip.
- [collector.py](collector.py) — skanowanie folderów output i budowa listy plików.
- [links.py](links.py) — trwałe linkowanie `render_run_id -> param_run_id` w `step_links.json`.
- [schemas.py](schemas.py) — modele Pydantic: `ExportFile`, `ExportManifest`.

## 2. Endpointy HTTP

Prefiks routera: `/api/air/export`

### 2.1. `GET /list/{render_run_id}`

Zwraca manifest eksportu (`ExportManifest`): listę plików do pobrania oraz listę brakujących kroków.

Query params:

- `param_run_id` (opcjonalnie): jeśli podasz, backend spróbuje dołączyć pliki param_generation właśnie z tego runa.

Zachowanie (zgodne z `router._build_manifest()`):

1) zbiera pliki renderu (`render/output/<render_run_id>/...`)
2) próbuje zebrać pliki MIDI dla runa o tym samym ID (szuka folderu kończącego się na `render_run_id`)
3) próbuje zebrać pliki param:
   - jeśli query zawiera `param_run_id` → używa go,
   - w przeciwnym razie próbuje rozwiązać `param_run_id` z linka w `step_links.json`.

Pole `missing` jest listą stringów, np. `"midi_generation"` lub `"param_generation"`.

### 2.2. `GET /zip/{render_run_id}`

Zwraca ZIP zawierający wszystkie znalezione pliki z manifestu.

Query params:

- `param_run_id` (opcjonalnie) — jak wyżej.

Szczegóły implementacyjne:

- ZIP jest budowany do `tempfile.SpooledTemporaryFile` (bufor w pamięci, potem ewentualnie na dysku).
- nazwy w ZIP są sanityzowane (`_safe_arcname`): usuwa `..`, ścieżki absolutne i normalizuje separatory.
- jeśli dwa pliki miałyby tę samą nazwę w ZIP, backend dodaje suffix `__N`.

## 3. Modele danych (`schemas.py`)

### 3.1. `ExportFile`

Pola publiczne (trafiają do API):

- `step`: `param_generation | midi_generation | render`
- `rel_path`: ścieżka względna w obrębie outputu danego kroku (lub folderu runa)
- `url`: URL do pobrania przez statyczny mount
- `bytes`: rozmiar pliku (best-effort)

Pole `abs_path` jest w modelu, ale ma `exclude=True`, więc nie jest zwracane w API.

### 3.2. `ExportManifest`

- `render_run_id`: wymagane
- `midi_run_id`: zwykle to samo co render, jeśli znaleziono folder
- `param_run_id`: jeśli udało się rozwiązać
- `files[]`: lista `ExportFile`
- `missing[]`: lista brakujących kroków

## 4. Skąd bierzemy pliki (layout outputów)

Moduł opiera się na tym, jak poprzednie kroki zapisują artefakty.

### 4.1. Render

Render jest spodziewany dokładnie w:

- `app/air/render/output/<render_run_id>/...`

Skanowanie: rekurencyjnie wszystkie pliki w folderze runa.

URL dla każdego pliku renderu:

- `/api/audio/<render_run_id>/<rel>`

To jest spójne z mountem w `main.py`:

- `app.mount("/api/audio", StaticFiles(directory=.../air/render/output))`

### 4.2. MIDI generation

MIDI output jest szukany po sufiksie run_id, bo folder bywa tworzony jako:

- `<timestamp>_<run_id>`

Skanowanie:

- znajduje katalog w `app/air/midi_generation/output/`, którego nazwa kończy się na `run_id`
- jeśli jest kilka, wybiera leksykograficznie “najnowszy” (największy prefix)

URL:

- `/api/midi-generation/output/<folder>/<rel>`

### 4.3. Param generation

Param output działa analogicznie jak MIDI:

- folder w `app/air/param_generation/output/` szukany po sufiksie `param_run_id`

URL:

- `/api/param-generation/output/<folder>/<rel>`

## 5. Linkowanie runów (render → param)

Ponieważ `render_run_id` jest stabilnym ID projektu w UI, a `param_generation` historycznie zapisuje outputy w folderach z prefixem timestampu, moduł trzyma mapowanie w osobnym pliku:

- `app/air/projects/output/step_links.json`

API helperów (`links.py`):

- `link_param_to_render(render_run_id, param_run_id)`
- `get_param_for_render(render_run_id) -> Optional[str]`

To mapowanie jest wykorzystywane przez export, jeśli caller nie poda `param_run_id`.

## 6. Błędy i edge-case’y

- Jeśli `render_run_id` jest pusty → HTTP 422 (`invalid_run_id`).
- Jeśli nie ma folderu renderu lub jest pusty → `missing` zawiera `"render"`, ale endpoint nadal zwróci manifest/ZIP (ZIP będzie po prostu miał mniej plików).
- ZIP/manifest są best-effort: pojedyncze pliki, których nie da się odczytać, są pomijane bez przerywania całego eksportu.
