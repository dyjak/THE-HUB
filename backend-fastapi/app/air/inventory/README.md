# AIR Inventory Module

Single source of truth for local sample catalog. All runtime modules should derive instrument lists and sample metadata from `inventory.json`.

## Files
- `inventory.json` – canonical catalog file; structure:
  - `schema_version`: string
  - `generated_at`: unix timestamp
  - `root`: absolute or project-root-relative path to sample root
  - `instruments`: object `{[instrumentName]: {count, examples[]}}`
  - `samples`: array of rows:
    - `instrument`: string
    - `id`: string (filename stem or unique id)
    - `file_abs`?: absolute path
    - `file_rel`?: path relative to `root`
    - optional metadata: `bytes`, `source`, `pitch`, `category`, `family`, `subtype`, `is_loop`, and, in deep inventories, `sample_rate`, `length_sec`

## Access API
Use `app.air.inventory.access`:
- `get_inventory_cached()` – read with in-memory cache
- `ensure_inventory(deep: bool = False)` – force rebuild and refresh cache
- `list_instruments()` – sorted instrument names from inventory
- `instrument_exists(name)` – boolean

## HTTP API
Mounted under `/api/air/inventory`:
- `GET /meta`
- `GET /available-instruments`
- `GET /inventory`
- `POST /rebuild` `{mode:"deep"?}`
- `GET /samples/{instrument}` – paginated sample listing with preview URLs

## Design principles
- No token maps or filesystem heuristics in production path. Everything flows from `inventory.json`.
- Backwards-compatible: if `file_abs` is not present, `file_rel` resolves against `root`.
- Extensible: new instruments or metadata fields can be added without changing code; downstream consumers should treat unknown fields as opaque.

## Notes
- Rebuild (`/rebuild`) is optional; if the catalog is maintained externally, simply drop a new `inventory.json` and restart the app (or call `ensure_inventory`).
