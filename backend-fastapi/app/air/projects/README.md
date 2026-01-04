# AIR (backend) — `projects`

Ten folder zawiera minimalne, plikowe mechanizmy pomocnicze związane z “projektem” w AIR.

W tej chwili nie ma tutaj routera FastAPI — to moduł narzędziowy.

## 1. Pliki w module

- [store.py](store.py) — prosty magazyn projektu jako JSON w `output/`.
- `output/` — katalog z zapisanymi projektami (`<project_id>.json`).

Uwaga integracyjna: w tym samym `output/` (ale poza tym modułem) jest też używany plik `step_links.json` (tworzony przez [air/export/links.py](../export/links.py)) do mapowania runów między krokami.

## 2. `store.py` — zapis/odczyt projektu

### 2.1. Lokalizacja danych

Pliki są przechowywane obok kodu, w:

- `app/air/projects/output/<project_id>.json`

### 2.2. `_project_path(project_id)`

Mapuje `project_id` na ścieżkę pliku JSON:

- `ROOT / f"{project_id}.json"`

### 2.3. `load_project(project_id)`

- Zwraca `dict` jeśli plik istnieje i da się sparsować.
- Zwraca `None` jeśli pliku nie ma albo JSON jest uszkodzony.

To jest celowo “best-effort” — brak wyjątków na zewnątrz.

### 2.4. `save_project(project_id, data)`

Zapis jest typu merge:

- jeśli plik istnieje → wczytuje poprzednią wersję (best-effort)
- wynik to `{**existing, **data}` (klucze z `data` nadpisują stare)
- zawsze dopisuje/ustawia `project_id` w wyniku
- zapisuje JSON z `ensure_ascii=False` i `indent=2`

Przykład semantyki merge:

- jeśli istnieje `{ "a": 1, "b": 2 }` i zapiszesz `{ "b": 5 }` → wynik to `{ "a": 1, "b": 5, "project_id": "..." }`.

## 3. Edge-case’y

- Moduł nie stosuje locków ani transakcji — równoległe zapisy tego samego `project_id` mogą się nadpisywać (typowe ograniczenie prostego file-store).
- Brak walidacji schematu danych projektu: to celowo “generic dict”.
