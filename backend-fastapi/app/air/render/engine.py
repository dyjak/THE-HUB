from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
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

# Base reference frequency for pitch-shifting (assume C4 for raw samples),
# kept in sync conceptually with the experimental audio_renderer.
_BASE_FREQ = 261.63 # C4
#_BASE_FREQ = 523.25  # C5


def _note_freq(midi_note: int) -> float:
    return 440.0 * (2 ** ((midi_note - 69) / 12.0))


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


def _pitch_shift_resample(samples: List[float], base_freq: float, target_freq: float) -> List[float]:
    """Simple resampling pitch-shift using numpy if available.

    If numpy is missing or base_freq invalid, returns the original samples.
    """

    try:
        import numpy as np  # type: ignore
    except Exception:  # pragma: no cover - environments without numpy
        return samples

    if base_freq <= 0.0:
        return samples

    ratio = target_freq / base_freq
    safe_ratio = max(ratio, 1e-6)
    new_len = max(1, int(len(samples) / safe_ratio))
    if new_len <= 1 or len(samples) <= 1:
        return samples

    indices = np.linspace(0, len(samples) - 1, new_len)
    return np.interp(indices, np.arange(len(samples)), np.array(samples, dtype="float32")).tolist()


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


def _resolve_sample_for_instrument(instrument: str, selected_samples: Dict[str, str] | None, lib: Dict[str, List[LocalSample]]) -> LocalSample | None:
    """Find the LocalSample for an instrument using selected_samples + inventory.

    selected_samples: instrument -> sample_id
    If no explicit selection, fall back to first sample in inventory for that instrument.
    """

    sample_id = (selected_samples or {}).get(instrument)
    if sample_id:
        s = find_sample_by_id(lib, instrument, sample_id)
        if s and s.file.exists():
            return s

    # fallback: first available
    for s in lib.get(instrument, []) or []:
        if s.file.exists():
            return s
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
    # Użytkownik może delikatnie dostroić długość fade-outu pomiędzy
    # kolejnymi nutami tego samego instrumentu. Zakres w sekundach,
    # defensywnie ograniczony do [0.0, 0.1].
    try:
        fadeout_sec = float(getattr(req, "fadeout_seconds", 0.01) or 0.0)
    except Exception:
        fadeout_sec = 0.01
    fadeout_sec = max(0.0, min(0.1, fadeout_sec))

    # Determine global song length (bars * 8 steps), inferred from MIDI if possible.
    # Jeśli dostępne jest per-instrument MIDI, bierzemy meta z globalnego MIDI,
    # który jest spójny dla wszystkich instrumentów (tempo, bars, length_seconds).
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
    missing_or_failed: List[str] = []

    # Basic set of percussive instrument names for which we skip pitch-shifting
    # and always play the raw sample (as in the experimental renderer).
    perc_set = {
        "kick",
        "snare",
        "hihat",
        "clap",
        "808",
        "tom",
        "perc",
        "cymbal",
        "ride",
        "crash",
        "rim",
        "hh",
        "hat",
    }

    # Mapowanie warstw per instrument:
    # - jeśli dostępne jest midi_per_instrument, bierzemy warstwę z odpowiedniego
    #   instancji MIDI,
    # - w przeciwnym razie używamy dotychczasowego rozwiązania: globalne midi.layers.
    global_layers = req.midi.get("layers") or {}
    if not isinstance(global_layers, dict):
        global_layers = {}

    for track in req.tracks:
        if not track.enabled:
            continue

        instrument = track.instrument
        sample = _resolve_sample_for_instrument(instrument, req.selected_samples, lib)
        if not sample:
            log.warning("[render] no sample for instrument=%s (selected=%s)", instrument, (req.selected_samples or {}).get(instrument))
            missing_or_failed.append(instrument)
            continue

        sample_path = sample.file
        base_wave = _read_wav_mono(sample_path)
        if base_wave is None or not base_wave:
            log.warning("[render] failed to read sample for instrument=%s path=%s", instrument, sample_path)
            missing_or_failed.append(instrument)
            continue

        # Optional per-sample loudness normalisation based on inventory analysis.
        try:
            if sample.gain_db_normalize is not None:
                gain = _db_to_gain(float(sample.gain_db_normalize))
                if gain > 0.0 and gain != 1.0:
                    base_wave = [v * gain for v in base_wave]
        except Exception:
            # Fail-silent: fall back to raw sample if anything goes wrong.
            pass

        # Build mono buffer for this instrument
        buf = [0.0] * frames
        # Prosta logika "voice stealing": kolejne zdarzenie tego samego
        # instrumentu może wejść w dowolnym momencie (zgodnie z MIDI), ale
        # ogon poprzedniego jest szybko wygaszany od chwili pojawienia się
        # nowego eventu (krótki fade-out zamiast twardego ucięcia).
        last_event_end = 0
        # Wybór warstwy MIDI: preferujemy midi_per_instrument, fallback na globalne layers.
        if req.midi_per_instrument and instrument in req.midi_per_instrument:
            inst_midi = req.midi_per_instrument[instrument] or {}
            layer = (inst_midi.get("layers") or {}).get(instrument, [])
        else:
            layer = global_layers.get(instrument, [])

        # Znormalizuj indeksy taktów tak, aby najwcześniejszy takt
        # zaczynał się od 0. Dzięki temu, jeśli generator MIDI
        # rozpoczyna pattern od bar=1 (lub większego), nie pojawi
        # się sztuczna cisza na początku wyrenderowanego stema.
        min_bar = 0
        try:
            if layer:
                min_bar = min(int(b.get("bar", 0)) for b in layer)
        except Exception:
            min_bar = 0
        total_events = sum(len((b.get("events") or [])) for b in (layer or []))
        log.info(
            "[render] instrument=%s bars=%d events=%d duration=%.2fs",
            instrument,
            len(layer or []),
            total_events,
            duration_sec,
        )

        # Determine per-sample base frequency for melodic instruments.
        # If inventory provided a numeric root_midi from FFT analysis,
        # use it; otherwise fall back to global _BASE_FREQ.
        base_freq = _BASE_FREQ
        try:
            rm = getattr(sample, "root_midi", None)
            if rm is not None:
                base_freq = _note_freq(int(round(float(rm))))
        except Exception:
            base_freq = _BASE_FREQ
        for bar in (layer or []):
            try:
                b = int(bar.get("bar", 0)) - int(min_bar)
            except Exception:
                b = 0
            for ev in bar.get("events", []):
                step = ev.get("step", 0)
                vel = float(ev.get("vel", 100)) / 127.0
                note = ev.get("note")
                start = (int(b) * 8 + int(step)) * step_samples_global
                if start >= frames:
                    continue

                # For percussive instruments or missing/invalid note, skip pitch shifting.
                pitched = base_wave
                try:
                    key = str(instrument).strip().lower()
                    if isinstance(note, int) and key not in perc_set:
                        pitched = _pitch_shift_resample(base_wave, base_freq, _note_freq(int(note)))
                except Exception:
                    pitched = base_wave

                nl = min(len(pitched), frames - start)
                if nl <= 0:
                    continue

                # Jeśli poprzednie zdarzenie jeszcze trwa w momencie startu
                # nowego, wykonujemy krótki fade-out jego ogona w przedziale
                # [start, last_event_end), aby uniknąć kliku i jednocześnie
                # nie dopuścić do długiego nakładania się ogonów.
                if last_event_end > start:
                    # długość wygaszania ogona poprzedniej nuty według
                    # parametru fadeout_seconds (domyślnie ok. 10 ms)
                    fade_len = min(int(fadeout_sec * sr), last_event_end - start)
                    if fade_len <= 0:
                        for idx in range(start, min(last_event_end, frames)):
                            buf[idx] = 0.0
                    else:
                        end_fade = start + fade_len
                        # 1) krótki liniowy fade-out istniejącego ogona
                        for i in range(fade_len):
                            idx = start + i
                            if idx >= frames:
                                break
                            t = i / float(max(fade_len - 1, 1))
                            buf[idx] *= max(0.0, 1.0 - t)
                        # 2) pozostałą część ogona (jeśli jest dłuższa niż fade)
                        # czyścimy do zera, żeby nie ciągnęła się za długo.
                        for idx in range(end_fade, min(last_event_end, frames)):
                            buf[idx] = 0.0

                # simple attack/release envelope dla nowego zdarzenia
                a = max(1, int(0.01 * sr))
                r = max(1, int(0.1 * sr))
                for i in range(nl):
                    amp = 1.0
                    if i < a:
                        amp = i / a
                    elif i > nl - r:
                        amp = max(0.0, (nl - i) / r)
                    buf[start + i] += pitched[i] * vel * amp

                # Zapisz koniec bieżącego zdarzenia (do ewentualnego duckingu
                # przy następnym evencie tego instrumentu).
                last_event_end = max(last_event_end, start + nl)

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
            missing_or_failed.append(instrument)
            continue

        stem_path = run_folder / f"{req.project_name}_{instrument}_{timestamp}.wav"
        _write_wav_stereo(stem_path, stem_l, stem_r, sr=sr)
        stems.append(RenderedStem(instrument=instrument, audio_rel=str(stem_path.relative_to(OUTPUT_ROOT.parent))))
        all_stems_l.append(stem_l)
        all_stems_r.append(stem_r)

    # If nothing rendered at all, fail loudly so frontend can show a clear error.
    if not stems:
        details = {
            "error": "render_no_instruments",
            "message": "Żaden instrument nie został wyrenderowany (brak lub błędne sample).",
        }
        if missing_or_failed:
            details["missing_or_failed"] = sorted(set(missing_or_failed))
        raise RuntimeError(str(details))

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
