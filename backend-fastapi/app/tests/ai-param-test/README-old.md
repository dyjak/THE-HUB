# ai_param_test (AI-Enhanced Local Module)

Local-only variant of the parametrized music generation test pipeline. This module removes all external API dependencies (Freesound / Wikimedia) and instead operates purely on WAV samples present under a project-level `local_samples/` directory. It now supports **real MIDI export (.mid)**, per-run JSON pattern dumps, **pianoroll PNG visualization**, a persistent **inventory** (schema v3) of discovered samples, **per-run output subdirectories**, a reproducible **selection snapshot**, and **strict validation** (unknown instruments rejected with HTTP 422).

## Endpoints (prefixed with /api)

| Method | Path | Description |
| ------ | ---- | ----------- |
| GET | `/ai-param-test/presets` | Available preset parameter bundles |
| GET | `/ai-param-test/meta` | Module metadata + schema version |
| GET | `/ai-param-test/available-instruments` | Quick flat list of currently discoverable instruments |
| GET | `/ai-param-test/inventory` | Detailed inventory (counts + filename examples). Auto-builds if missing. |
| POST | `/ai-param-test/inventory/rebuild` | Force rebuild of inventory.json |
| POST | `/ai-param-test/run/midi` | Generate MIDI pattern, export JSON + optional `.mid`, PNG pianoroll |
| POST | `/ai-param-test/run/render` | Generate MIDI + strict local sample selection + audio render |
| POST | `/ai-param-test/run/full` | Alias of render (parity naming) |
| GET | `/ai-param-test/debug/{run_id}` | Retrieve structured debug timeline |
| Static | `/api/ai-param-test/output/*` | Served artifacts: `.json`, `.mid`, `.png`, `.wav` |

> Strict validation: All run endpoints reject unknown instruments with `HTTP 422` and payload `{ "error": "unknown_instruments", "unknown": [...], "available": [...] }`.

## Request Payload Examples

Generate minimal MIDI pattern:
```jsonc
POST /api/ai-param-test/run/midi
{
  "genre": "ambient",
  "mood": "calm",
  "tempo": 80,
  "key": "C",
  "scale": "major",
  "instruments": ["piano"],
  "bars": 4,
  "seed": 123
}
```

Full render (explicit split object accepted by /run/render and /run/full):
```jsonc
POST /api/ai-param-test/run/render
{
  "midi": {"bars": 8, "instruments": ["piano", "pad"], "tempo": 90},
  "audio": {"seconds": 6, "sample_rate": 44100}
}
```

## Local Sample Discovery & Strictness

Place WAV files inside `backend-fastapi/local_samples/` (or nested). Naming heuristics map filenames → instruments (substring match). Granular percussion tokens are treated as *separate* instruments so you can request them independently:

`piano`, `pad`, `string`, `guitar`, `bass`, `lead`, `choir`, `flute`, `trumpet`, `sax`, plus drums: `kick`, `snare`, `hihat`, `clap`, `rim`, `tom`, `808`, `perc`, and generic `drum`, `drumkit`.

Unmatched fall into a `misc` bucket but are not auto-selected unless explicitly requested with matching heuristic.

Strict mode: If any requested instrument lacks at least one discovered sample, the render/full run aborts with `SampleMissingError` (422 if pre-validation catches it). No synthetic / placeholder samples are generated.

Selection is deterministic (sorted list index) so same parameters + same sample set → identical selection.

## MIDI Representation & Visualization

Per run we create a unique directory:

`output/<UTC_TS>_<RUN_ID>/`

Inside it (relative names also returned with `_rel` fields):

| Artifact | Filename | Notes |
| -------- | -------- | ----- |
| JSON Pattern | `midi.json` | Full structured internal pattern (bars / events) |
| Standard MIDI | `midi.mid` | Single-track export (quantized 8 steps/bar) using `mido` if installed |
| Piano Roll PNG | `pianoroll_<run>.png` | Combined events scatter visualization |
| Audio Mix | `audio.wav` | Mono mixed render of selected instrument samples |

If `mido` or `matplotlib` are not available, respective artifacts are skipped and debug events record the omission.

## Inventory (schema v3)

`inventory.json` (module directory) now uses **schema_version: "3"** and stores both a concise instrument summary and a flat `samples` array with extended metadata:

```jsonc
{
  "schema_version": "3",
  "generated_at": 1727280000.123,
  "root": "/abs/path/local_samples",
  "instrument_count": 12,
  "total_files": 57,
  "total_bytes": 123456789,
  "deep": false,
  "instruments": {
    "piano": { "count": 4, "examples": ["soft_piano1.wav", "soft_piano2.wav"] },
    "kick": { "count": 8, "examples": ["kick_deep.wav", "kick_soft.wav"] }
  },
  "samples": [
    {
      "instrument": "piano",
      "id": "soft_piano1",
      "file_rel": "keys/piano/soft_piano1.wav",
      "file_abs": "/abs/.../soft_piano1.wav",
      "bytes": 345678,
      "source": "local",
      "pitch": "F",
      "category": "instrument",
      "family": "melodic",
      "subtype": "piano",
      "is_loop": false
    },
    {
      "instrument": "kick",
      "id": "kick_deep",
      "file_rel": "drums/kick/kick_deep.wav",
      "file_abs": "/abs/.../kick_deep.wav",
      "bytes": 12345,
      "source": "local",
      "pitch": null,
      "category": "oneshot",
      "family": "drum",
      "subtype": "kick",
      "is_loop": false
    }
  ]
}
```

Deep scan: `POST /api/ai-param-test/inventory/rebuild?mode=deep` populates `sample_rate` + `length_sec` inside each sample object and sets `deep: true`.

Frontend nadal używa uproszczonego widoku; można rozszerzyć o filtry po `family` / `category`.

### Selection Snapshot

Każdy run renderujący audio zapisuje `selection.json` w swoim katalogu per-run:
```jsonc
{
  "run_id": "ab12cd",
  "instruments": ["kick","snare","bass"],
  "samples": [
    {"instrument": "kick", "file": "/abs/.../kick_deep.wav", "subtype": "kick", "family": "drum"},
    {"instrument": "snare", "file": "/abs/.../snare_crisp.wav", "subtype": "snare", "family": "drum"}
  ]
}
```
To pozwala w 100% odtworzyć miks później.

## Debug Events

Every run collects a timeline of structured events (stage, message, data). Retrieve via:
`GET /api/ai-param-test/debug/{run_id}`.

## Git Ignore

The `.gitignore` has been updated to exclude:
- `local_samples/`
- generated `output/` directories
- common audio (`*.wav`) & MIDI (`*.mid`) artifacts

## Roadmap / Possible Enhancements
- Per-layer multi-track MIDI export
- Individual layer pianoroll sprites (current: combined only)
- Configurable instrument ↔ filename mapping (JSON / env)
- More advanced rhythmic / chordal generation
- Optional stem caching & re-use (avoid re-render when same sample+events)
- Hash-based content addressing for identical pattern outputs
- Frontend filtracja po family/category/pitch

## Version & Schema
Schema version exposed under `/ai-param-test/meta`: `2025-10-05-1` (niezależna od inventory `schema_version` = `3`).

Increment the date-stamped suffix on any breaking API response shape change; bump `inventory` schema_version independently for compendium shape changes.
