from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List, Tuple
import logging
import math
import wave
import struct
import time

from .schemas import RenderRequest, RenderResponse, RenderedStem, TrackSettings
from ..inventory.local_library import discover_samples, find_sample_by_id, LocalSample


OUTPUT_ROOT = Path(__file__).parent / "output"
OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

log = logging.getLogger("air.render")


def _db_to_gain(db: float) -> float:
    return math.pow(10.0, db / 20.0)


def _pan_gains(pan: float) -> Tuple[float, float]:
    """Simple constant-power panning.

    pan=-1 -> full left, pan=1 -> full right.
    """

    pan = max(-1.0, min(1.0, pan))
    angle = (pan + 1.0) * math.pi / 4.0
    left = math.cos(angle)
    right = math.sin(angle)
    return left, right


def _read_wav_mono(path: Path) -> List[float] | None:
    """Read mono PCM samples from WAV.

    We first try scipy for broader codec support; if unavailable or failing,
    fall back to the built-in wave module with 16-bit PCM only.
    """

    try:
        import scipy.io.wavfile as wavfile  # type: ignore
        import numpy as _np  # type: ignore

        sr, data = wavfile.read(str(path))
        if hasattr(data, "shape") and len(getattr(data, "shape", ())) > 1:
            data = data[:, 0]
        if hasattr(data, "dtype"):
            if data.dtype.kind in ("i", "u"):
                maxv = float(_np.iinfo(data.dtype).max)
                data = data.astype("float32") / (maxv if maxv else 1.0)
            elif data.dtype.kind == "f":
                data = data.astype("float32")
        return _np.asarray(data, dtype="float32").tolist()
    except Exception:
        try:
            with wave.open(str(path), "rb") as wf:
                n_channels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                n_frames = wf.getnframes()
                if sampwidth != 2:
                    return None
                raw = wf.readframes(n_frames)
                total_samples = n_frames * n_channels
                fmt = "<" + "h" * total_samples
                ints = struct.unpack(fmt, raw)
                mono = ints[0::n_channels]
                return [v / 32768.0 for v in mono]
        except Exception:
            return None


def _write_wav_stereo(path: Path, left: List[float], right: List[float], sr: int = 44100) -> None:
    n = min(len(left), len(right))
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        frames = bytearray()
        for i in range(n):
            l = max(-1.0, min(1.0, left[i]))
            r = max(-1.0, min(1.0, right[i]))
            frames.extend(struct.pack("<h", int(l * 32767)))
            frames.extend(struct.pack("<h", int(r * 32767)))
        w.writeframes(frames)


def _mix_tracks(tracks: List[List[float]]) -> List[float]:
    length = max((len(t) for t in tracks), default=0)
    if length == 0:
        return []
    out = [0.0] * length
    for t in tracks:
        for i, v in enumerate(t):
            out[i] += v
    # simple normalization to avoid clipping
    peak = max((abs(v) for v in out), default=1.0)
    if peak > 0:
        scale = 0.9 / peak
        out = [v * scale for v in out]
    return out


def _resolve_sample_for_instrument(instrument: str, selected_samples: Dict[str, str] | None, lib: Dict[str, List[LocalSample]]) -> Path | None:
    """Find the WAV file for an instrument using selected_samples + inventory.

    selected_samples: instrument -> sample_id
    If no explicit selection, fall back to first sample in inventory for that instrument.
    """

    sample_id = (selected_samples or {}).get(instrument)
    if sample_id:
        s = find_sample_by_id(lib, instrument, sample_id)
        if s and s.file.exists():
            return s.file

    # fallback: first available
    for s in lib.get(instrument, []) or []:
        if s.file.exists():
            return s.file
    return None


def render_audio(req: RenderRequest) -> RenderResponse:
    """Render audio mix and per-instrument stems based on MIDI + inventory.

    For each enabled track (instrument) we:
    - resolve a sample WAV via inventory + selected_samples,
    - build a mono buffer from MIDI layers by pasting that sample on the timeline,
    - apply a simple envelope per event,
    - then apply volume + pan and write a stereo stem.
    Finally we normalize and mix all stems into a stereo master.
    """

    log.info(
        "[render] start project=%s run_id=%s tracks=%s",
        req.project_name,
        req.run_id,
        [t.instrument for t in req.tracks],
    )

    sr = 44100

    # Determine global song length (bars * 8 steps), inferred from MIDI if possible.
    meta = req.midi.get("meta") or {}
    bars = None
    try:
        if isinstance(meta.get("bars"), int) and meta.get("bars") > 0:
            bars = int(meta.get("bars"))
    except Exception:
        bars = None
    if not bars:
        try:
            max_bar = -1
            pattern = req.midi.get("pattern") or []
            for bar in pattern:
                try:
                    b = int(bar.get("bar", 0))
                    max_bar = max(max_bar, b)
                except Exception:
                    pass
            layers = req.midi.get("layers") or {}
            if isinstance(layers, dict):
                for _inst, layer in layers.items():
                    try:
                        for bar in (layer or []):
                            b = int(bar.get("bar", 0))
                            max_bar = max(max_bar, b)
                    except Exception:
                        continue
            bars = (max_bar + 1) if max_bar >= 0 else 1
        except Exception:
            bars = 1
    total_steps = max(1, int(bars) * 8)

    # Derive duration from meta.length_seconds if present, else from bars (2s per bar fallback).
    duration_sec = None
    try:
        if isinstance(meta, dict) and "length_seconds" in meta:
            duration_sec = float(meta.get("length_seconds") or 0.0)
    except Exception:
        duration_sec = None
    if not duration_sec or not (0.5 <= duration_sec <= 3600.0):
        duration_sec = max(1.0, float(bars) * 2.0)

    frames = int(sr * duration_sec)
    step_samples_global = max(1, int(frames / total_steps))

    run_folder = OUTPUT_ROOT / req.run_id
    run_folder.mkdir(parents=True, exist_ok=True)
    timestamp = int(time.time())

    # Load inventory once
    lib = discover_samples(deep=False)
    log.info("[render] inventory loaded instruments=%s", sorted(lib.keys()))

    stems: List[RenderedStem] = []
    all_stems_l: List[List[float]] = []
    all_stems_r: List[List[float]] = []

    layers_map = req.midi.get("layers") or {}
    if not isinstance(layers_map, dict):
        layers_map = {}

    for track in req.tracks:
        if not track.enabled:
            continue

        instrument = track.instrument
        sample_path = _resolve_sample_for_instrument(instrument, req.selected_samples, lib)
        if not sample_path:
            log.warning("[render] no sample for instrument=%s (selected=%s)", instrument, (req.selected_samples or {}).get(instrument))
            continue

        base_wave = _read_wav_mono(sample_path)
        if base_wave is None or not base_wave:
            log.warning("[render] failed to read sample for instrument=%s path=%s", instrument, sample_path)
            continue

        # Build mono buffer for this instrument
        buf = [0.0] * frames
        layer = layers_map.get(instrument, [])
        total_events = sum(len((b.get("events") or [])) for b in (layer or []))
        log.info(
            "[render] instrument=%s bars=%d events=%d duration=%.2fs",
            instrument,
            len(layer or []),
            total_events,
            duration_sec,
        )
        for bar in (layer or []):
            b = bar.get("bar", 0)
            for ev in bar.get("events", []):
                step = ev.get("step", 0)
                vel = float(ev.get("vel", 100)) / 127.0
                start = (int(b) * 8 + int(step)) * step_samples_global
                if start >= frames:
                    continue
                nl = min(len(base_wave), frames - start)
                if nl <= 0:
                    continue
                # simple attack/release envelope
                a = max(1, int(0.01 * sr))
                r = max(1, int(0.1 * sr))
                for i in range(nl):
                    amp = 1.0
                    if i < a:
                        amp = i / a
                    elif i > nl - r:
                        amp = max(0.0, (nl - i) / r)
                    buf[start + i] += base_wave[i] * vel * amp

        # Apply volume + pan and write stereo stem
        gain = _db_to_gain(track.volume_db)
        pan_l, pan_r = _pan_gains(track.pan)
        stem_l: List[float] = []
        stem_r: List[float] = []
        for s in buf:
            v = s * gain
            stem_l.append(v * pan_l)
            stem_r.append(v * pan_r)

        if not stem_l or not stem_r:
            continue

        stem_path = run_folder / f"{req.project_name}_{instrument}_{timestamp}.wav"
        _write_wav_stereo(stem_path, stem_l, stem_r, sr=sr)
        stems.append(RenderedStem(instrument=instrument, audio_rel=str(stem_path.relative_to(OUTPUT_ROOT.parent))))
        all_stems_l.append(stem_l)
        all_stems_r.append(stem_r)

    # Build mix from all stereo stems
    if all_stems_l and all_stems_r:
        mix_l = _mix_tracks(all_stems_l)
        mix_r = _mix_tracks(all_stems_r)
    else:
        # no enabled/usable tracks -> silence
        mix_l = [0.0] * frames
        mix_r = [0.0] * frames

    mix_path = run_folder / f"{req.project_name}_mix_{timestamp}.wav"
    _write_wav_stereo(mix_path, mix_l, mix_r, sr=sr)

    log.info(
        "[render] done project=%s run_id=%s mix=%s stems=%d duration=%.2fs",
        req.project_name,
        req.run_id,
        mix_path,
        len(stems),
        duration_sec,
    )

    return RenderResponse(
        project_name=req.project_name,
        run_id=req.run_id,
        mix_wav_rel=str(mix_path.relative_to(OUTPUT_ROOT.parent)),
        stems=stems,
        sample_rate=sr,
        duration_seconds=duration_sec,
    )
