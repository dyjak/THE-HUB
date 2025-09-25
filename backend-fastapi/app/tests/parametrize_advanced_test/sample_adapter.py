from __future__ import annotations
from typing import Dict, Any, List
from pathlib import Path

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
    """Selects and downloads one sample per instrument.
    Returns: { "samples": [ { "instrument": str, "id": str, "file": str, ... }, ... ] }
    """
    log("call", "prepare_samples", {"module": "sample_adapter.py", "instruments": instruments, "genre": genre, "mood": mood})
    _ensure_dirs()

    if SampleFetcher is None:
        try:
            from ..sample_fetcher import SampleFetcher as SF  # type: ignore
            from ..sample_fetcher import SampleInfo as SI  # type: ignore
            fetcher = SF()
        except Exception as e:  # pragma: no cover
            log("samples", "fetcher_unavailable", {"error": str(e)})
            return {"samples": []}
    else:
        fetcher = SampleFetcher()

    try:
        has_key = bool(getattr(fetcher, 'freesound_api_key', None))
        log("samples", "freesound_status", {"has_key": has_key})
    except Exception:
        pass

    chosen: List[Dict[str, Any]] = []
    # Attempt to use genre-specific mappings if available
    by_genre = None
    try:
        if genre:
            # Przekaż mood aby zbiasować wyszukiwanie
            by_genre = fetcher.get_samples_for_genre(genre, mood=mood)
    except Exception:
        by_genre = None

    missing: List[str] = []
    for inst in instruments:
        pick = None
        # Prefer genre mapping
        if by_genre and inst in by_genre and by_genre[inst]:
            pick = by_genre[inst][0]
        else:
            # Jeśli mamy klucz Freesound – nie używaj basic fallback (strict real-sample policy)
            has_key = getattr(fetcher, 'freesound_api_key', None)
            if not has_key:
                basics = fetcher.get_basic_samples()
                candidates = [s for s in basics.values() if getattr(s, 'instrument', None) == inst]
                if candidates:
                    pick = candidates[0]

        if pick is None:
            log("samples", "instrument_no_sample", {"instrument": inst})
            missing.append(inst)
            continue

        try:
            file_path = fetcher.download_sample(pick, output_dir=str(SAMPLES_DIR))
        except Exception as e:
            log("samples", "download_failed", {"instrument": inst, "error": str(e)})
            missing.append(inst)
            continue

        entry = {
            "instrument": inst,
            "id": getattr(pick, 'id', inst),
            "name": getattr(pick, 'name', inst),
            "file": file_path,
            "source": getattr(pick, 'source', None),
            "origin_url": getattr(pick, 'origin_url', None),
        }
        chosen.append(entry)
        log("samples", "instrument_sample_ready", {"instrument": inst, "file": file_path, "source": entry["source"], "origin_url": entry["origin_url"]})

    if missing:
        raise SampleSelectionError(f"Missing samples for instruments: {', '.join(missing)}")
    log("samples", "prepared", {"count": len(chosen)})
    return {"samples": chosen}
