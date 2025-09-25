# parametrize_sampling_test (Local Sample Module)

Local-only variant of the parametrized music generation test pipeline. This module removes all external API dependencies (Freesound / Wikimedia) and instead operates purely on WAV samples present under a project-level `local_samples/` directory.

## Endpoints (prefixed with /api)

- `GET  /param-sampling/presets` – available preset parameter bundles
- `GET  /param-sampling/meta` – module metadata
- `POST /param-sampling/run/midi` – generate MIDI-like pattern JSON only
- `POST /param-sampling/run/render` – generate MIDI + audio (same as full)
- `POST /param-sampling/run/full` – alias of render
- `GET  /param-sampling/debug/{run_id}` – retrieve debug event timeline
- Static artifacts: `/api/param-sampling/output/*` (JSON midi dumps + WAV previews)

## Request Payload Examples

Generate minimal MIDI pattern:
```jsonc
POST /api/param-sampling/run/midi
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
POST /api/param-sampling/run/render
{
  "midi": {"bars": 8, "instruments": ["piano", "pad"], "tempo": 90},
  "audio": {"seconds": 6, "sample_rate": 44100}
}
```

## Local Sample Discovery

Place WAV files inside `backend-fastapi/local_samples/` or nested folders. Naming heuristics map filenames to instruments:
- Filenames containing `piano`, `pad`, `string`, `guitar`, `drum`, `bass`, `lead` etc. will map accordingly.
- Unmatched files fall back to `misc` bucket.

The system deterministically selects a sample per instrument (stable ordering) so repeated runs with same parameters are reproducible.

## MIDI Representation

MIDI data is currently stored as JSON (`midi_<timestamp>_<runid>.json`) in the module `output/` directory. A real `.mid` export can be added later if needed.

## Debug Events

Every run collects a timeline of structured events (stage, message, data). Retrieve them via:
`GET /api/param-sampling/debug/{run_id}`

## Git Ignore

The `.gitignore` has been updated to exclude:
- `local_samples/`
- generated `output/` directories
- common audio (`*.wav`) & MIDI (`*.mid`) artifacts

## Roadmap / Possible Enhancements
- Optional piano-roll PNG renderer
- Real MIDI file export using `mido`
- Configurable instrument ↔ filename mapping (JSON / env)
- More advanced layering & rhythmic variation
- Per-run subdirectories for artifacts

## Version
Schema version exposed under `/param-sampling/meta`: `2025-09-25-1`
