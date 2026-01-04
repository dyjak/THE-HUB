from __future__ import annotations
from typing import Dict, Any, List
from pathlib import Path
import os
import json

try:
    from ..sample_fetcher import SampleFetcher, SampleInfo  # type: ignore
except Exception:
    # Fallback: relative import may fail in some contexts; handle at runtime in prepare_samples
    SampleFetcher = None  # type: ignore
    SampleInfo = None  # type: ignore


OUTPUT_DIR = Path(__file__).parent / "output"
SAMPLES_DIR = OUTPUT_DIR / "samples"


def _ensure_dirs():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)


class SampleSelectionError(RuntimeError):
    pass


def prepare_samples(instruments: List[str], genre: str | None, log, mood: str | None = None) -> Dict[str, Any]:
    """Selects and downloads one sample per instrument (multi-candidate, strict real-sample policy).
    Strategy:
      1. Use genre-based candidate lists (freesound/commons) via SampleFetcher.
      2. Iterate over candidates up to SAMPLE_MAX_CANDIDATES.
      3. For each candidate attempt download (with SAMPLE_DOWNLOAD_RETRIES simple retry loop).
      4. On first success accept and stop for that instrument.
      5. If no candidate succeeded:
           - If no freesound key: fallback to generated basic samples (still iterate) unless disabled by env SAMPLE_DISABLE_BASIC.
           - Else (key present) -> instrument considered missing (strict mode).
    Logs (stage=samples):
      - freesound_status
      - instrument_candidate_list (instrument, count)
      - instrument_sample_attempt (instrument, candidate_index, id, source, retry, remaining_candidates)
      - download_failed (existing)
      - instrument_sample_ready (existing)
      - instrument_no_sample (extended: attempts, fail_ids, last_error)
      - prepared (summary)
    Environment variables:
      SAMPLE_MAX_CANDIDATES (int, default 6)
      SAMPLE_DOWNLOAD_RETRIES (int, default 1)
      SAMPLE_DISABLE_BASIC ("1" to forbid basic fallback even without key)
    Returns: {"samples": [...]}
    Raises SampleSelectionError with reduced JSON details on missing instruments.
    """
    log("call", "prepare_samples", {"module": "sample_adapter.py", "instruments": instruments, "genre": genre, "mood": mood})
    _ensure_dirs()

    if SampleFetcher is None:
        try:  # late import fallback
            from ..sample_fetcher import SampleFetcher as SF  # type: ignore
            from ..sample_fetcher import SampleInfo as SI  # type: ignore
            fetcher = SF()
        except Exception as e:  # pragma: no cover
            log("samples", "fetcher_unavailable", {"error": str(e)})
            return {"samples": []}
    else:
        fetcher = SampleFetcher()

    # Config via env
    try:
        max_candidates = int(os.environ.get("SAMPLE_MAX_CANDIDATES", "6"))
    except ValueError:
        max_candidates = 6
    try:
        dl_retries = int(os.environ.get("SAMPLE_DOWNLOAD_RETRIES", "1"))
    except ValueError:
        dl_retries = 1
    disable_basic = os.environ.get("SAMPLE_DISABLE_BASIC", "0") == "1"

    has_key = bool(getattr(fetcher, 'freesound_api_key', None))
    log("samples", "freesound_status", {"has_key": has_key, "max_candidates": max_candidates, "download_retries": dl_retries, "basic_fallback": (not has_key and not disable_basic)})

    # Acquire genre based candidates
    by_genre: Dict[str, List[Any]] | None = None
    try:
        if genre:
            by_genre = fetcher.get_samples_for_genre(genre, mood=mood)
    except Exception as e:
        log("samples", "genre_fetch_failed", {"error": str(e)})
        by_genre = None

    chosen: List[Dict[str, Any]] = []
    missing: List[str] = []
    fail_reasons: Dict[str, List[Dict[str, str]]] = {}

    for inst in instruments:
        candidates: List[Any] = []
        if by_genre and inst in by_genre and by_genre[inst]:
            candidates = by_genre[inst][:max_candidates]
        else:
            # Only allow basic when no freesound key and not disabled
            if not has_key and not disable_basic:
                basics = fetcher.get_basic_samples()
                candidates = [s for s in basics.values() if getattr(s, 'instrument', None) == inst][:max_candidates]
        log("samples", "instrument_candidate_list", {"instrument": inst, "count": len(candidates)})

        if not candidates:
            missing.append(inst)
            log("samples", "instrument_no_sample", {"instrument": inst, "attempts": 0, "fail_ids": []})
            continue

        success_entry: Dict[str, Any] | None = None
        fail_reasons[inst] = []
        for idx, cand in enumerate(candidates):
            cand_id = getattr(cand, 'id', f"{inst}_{idx}")
            source = getattr(cand, 'source', None)
            for attempt in range(1, dl_retries + 1):
                log("samples", "instrument_sample_attempt", {
                    "instrument": inst,
                    "candidate_index": idx,
                    "id": cand_id,
                    "source": source,
                    "retry": attempt,
                    "remaining_candidates": len(candidates) - idx - 1
                })
                try:
                    file_path = fetcher.download_sample(cand, output_dir=str(SAMPLES_DIR))
                    # Basic integrity check
                    if not file_path or not Path(file_path).exists() or Path(file_path).stat().st_size < 48:
                        raise RuntimeError("file_invalid_or_too_small")
                    success_entry = {
                        "instrument": inst,
                        "id": cand_id,
                        "name": getattr(cand, 'name', cand_id),
                        "file": file_path,
                        "source": source,
                        "origin_url": getattr(cand, 'origin_url', None),
                    }
                    chosen.append(success_entry)
                    log("samples", "instrument_sample_ready", {"instrument": inst, "file": file_path, "source": source, "id": cand_id})
                    break  # break retry loop
                except Exception as e:  # capture failure
                    err_txt = str(e)
                    fail_reasons[inst].append({"id": cand_id, "source": str(source), "error": err_txt})
                    log("samples", "download_failed", {"instrument": inst, "candidate_index": idx, "id": cand_id, "error": err_txt})
            if success_entry:
                break  # break candidate loop

        if not success_entry:
            missing.append(inst)
            last_error = fail_reasons[inst][-1]["error"] if fail_reasons[inst] else None
            log("samples", "instrument_no_sample", {
                "instrument": inst,
                "attempts": len(fail_reasons[inst]),
                "fail_ids": [f["id"] for f in fail_reasons[inst]],
                "last_error": last_error,
            })

    if missing:
        # Build compact diagnostics
        diag = {m: fail_reasons.get(m, []) for m in missing}
        # Keep message short (strip errors to first 60 chars)
        compact = {k: [{"id": fr["id"], "src": fr["source"], "err": fr["error"][:60]} for fr in v[:5]] for k, v in diag.items()}
        raise SampleSelectionError(
            f"Missing samples for instruments: {', '.join(missing)} | details={json.dumps(compact, ensure_ascii=False)}"
        )

    log("samples", "prepared", {"count": len(chosen)})
    return {"samples": chosen}
