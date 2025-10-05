from __future__ import annotations
from typing import Dict, Any, List
import wave, struct, math
from pathlib import Path
import os

try:
    import numpy as np  # type: ignore
except Exception:
    np = None  # type: ignore


def _note_freq(midi_note: int) -> float:
    return 440.0 * (2 ** ((midi_note - 69) / 12.0))

def _pitch_shift_resample(samples: List[float], base_freq: float, target_freq: float) -> List[float]:
    if np is None or base_freq <= 0:
        return samples
    ratio = target_freq / base_freq
    new_len = max(1, int(len(samples) / max(ratio, 1e-6)))
    indices = np.linspace(0, len(samples) - 1, new_len)
    return np.interp(indices, np.arange(len(samples)), np.array(samples)).tolist()

def _mix_tracks(tracks: List[List[float]], gain: float = 0.8) -> List[float]:
    length = max((len(t) for t in tracks), default=0)
    if length == 0:
        return []
    out = [0.0] * length
    for t in tracks:
        for i, v in enumerate(t):
            out[i] += v
    peak = max((abs(v) for v in out), default=1.0)
    if peak > 0:
        scale = gain / peak
        out = [v * scale for v in out]
    return out

class SampleMissingError(RuntimeError):
    pass

def _read_wav_mono(path: Path) -> List[float] | None:
    # Prefer scipy for broad codec support
    try:
        import scipy.io.wavfile as wavfile  # type: ignore
        import numpy as _np  # type: ignore
        sr, data = wavfile.read(str(path))
        # stereo -> mono first channel
        if hasattr(data, 'shape') and len(getattr(data, 'shape', ())) > 1:
            data = data[:, 0]
        # normalize depending on dtype
        if hasattr(data, 'dtype'):
            if data.dtype.kind in ('i', 'u'):  # integer PCM
                maxv = float(_np.iinfo(data.dtype).max)
                data = data.astype('float32') / (maxv if maxv else 1.0)
            elif data.dtype.kind == 'f':  # already float PCM
                data = data.astype('float32')
        return _np.asarray(data, dtype='float32').tolist()
    except Exception:
        # Fallback: basic 16-bit PCM reader using wave
        try:
            import wave, struct
            with wave.open(str(path), 'rb') as wf:
                n_channels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                n_frames = wf.getnframes()
                if sampwidth != 2:
                    return None  # only 16-bit fallback supported
                raw = wf.readframes(n_frames)
                total_samples = n_frames * n_channels
                fmt = '<' + 'h' * total_samples
                ints = struct.unpack(fmt, raw)
                # pick first channel
                mono = ints[0::n_channels]
                return [v / 32768.0 for v in mono]
        except Exception:
            return None

BASE_FREQ = 261.63  # assume C4 for raw samples


def render_audio(audio_params: Dict[str, Any], midi: Dict[str, Any], samples: Dict[str, Any], log, run_id: str | None = None, run_dir: Path | None = None):
    sr = audio_params.get("sample_rate", 44100)
    seconds = audio_params.get("seconds", 5.0)
    frames = int(sr * seconds)
    base_output = Path(__file__).parent / "output"
    base_output.mkdir(parents=True, exist_ok=True)
    if run_dir is None:
        # fallback: flat structure (legacy)
        run_dir = base_output
    run_dir.mkdir(parents=True, exist_ok=True)
    wav_path = run_dir / "audio.wav"
    instruments: List[str] = midi.get("meta", {}).get("instruments", [])
    sample_map: Dict[str, str] = {s.get("instrument"): s.get("file") for s in samples.get("samples", [])}
    log("audio", "render_start", {"instruments": instruments, "sample_count": len(sample_map)})
    tracks: List[List[float]] = []
    per_instrument_tracks: dict[str, List[float]] = {}
    missing: List[str] = []
    for inst in instruments:
        file = sample_map.get(inst)
        if not file or not Path(file).exists():
            missing.append(inst)
            log("audio", "sample_missing", {"instrument": inst, "file": file})
            continue
        base_wave = _read_wav_mono(Path(file))
        if base_wave is None:
            missing.append(inst)
            log("audio", "sample_load_failed", {"instrument": inst, "file": file})
            continue
        buf = [0.0]*frames
        layer = midi.get("layers", {}).get(inst, [])
        step_samples = int(sr * (seconds / max(1, len(layer) * 8)))
        for bar in layer:
            b = bar.get("bar", 0)
            for ev in bar.get("events", []):
                step = ev.get("step", 0)
                note = ev.get("note")
                vel = ev.get("vel", 100) / 127.0
                start = (b*8 + step)*step_samples
                if start >= frames:
                    continue
                pitched = _pitch_shift_resample(base_wave, BASE_FREQ, _note_freq(note)) if np is not None else base_wave
                nl = min(len(pitched), frames-start)
                if nl <= 0:
                    continue
                a = max(1, int(0.01*sr))
                r = max(1, int(0.1*sr))
                for i in range(nl):
                    amp = 1.0
                    if i < a: amp = i/a
                    elif i > nl-r: amp = max(0.0, (nl-i)/r)
                    buf[start+i] += pitched[i]*vel*amp
        # after processing this instrument's layer, store its buffer
        tracks.append(buf)
        per_instrument_tracks[inst] = buf
    if missing:
        raise SampleMissingError(f"Missing samples for: {', '.join(missing)}")
    if not tracks:
        raise SampleMissingError("No audio rendered")
    mixed = _mix_tracks(tracks, gain=0.9)
    with wave.open(str(wav_path), 'w') as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
        for v in mixed:
            wf.writeframes(struct.pack('<h', int(max(-1,min(1,v))*32767)))
    log("audio", "render_done", {"file": str(wav_path), "bytes": wav_path.stat().st_size})
    rel_path = None
    try:
        rel_path = str(wav_path.relative_to(base_output))
    except Exception:
        rel_path = wav_path.name
    # Export per-instrument stems
    stems_abs: dict[str, str] = {}
    stems_rel: dict[str, str] = {}
    for inst, buf in per_instrument_tracks.items():
        try:
            safe = ''.join(c if (c.isalnum() or c in ('-', '_')) else '-' for c in str(inst).lower())
            stem_path = run_dir / f"stem_{safe}.wav"
            with wave.open(str(stem_path), 'w') as wf:
                wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
                for v in buf:
                    wf.writeframes(struct.pack('<h', int(max(-1,min(1,v))*32767)))
            stems_abs[inst] = str(stem_path)
            try:
                stems_rel[inst] = str(stem_path.relative_to(base_output))
            except Exception:
                stems_rel[inst] = stem_path.name
            log("audio", "stem_saved", {"instrument": inst, "file": stems_abs[inst]})
        except Exception as e:
            log("audio", "stem_failed", {"instrument": inst, "error": str(e)})
    return {"audio_file": str(wav_path), "audio_file_rel": rel_path, "stems": stems_abs, "stems_rel": stems_rel}
