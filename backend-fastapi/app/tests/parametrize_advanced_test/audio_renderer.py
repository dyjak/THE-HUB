from __future__ import annotations
from typing import Dict, Any, List
import math
import wave
import struct
from pathlib import Path
import os

try:
    import numpy as np  # type: ignore
    from scipy.io.wavfile import read as wav_read  # type: ignore
except Exception:
    np = None  # type: ignore
    wav_read = None  # type: ignore


def _load_wav_mono(file_path: str, target_sr: int) -> List[float] | None:
    if wav_read is None:
        return None
    try:
        sr, data = wav_read(file_path)
        if hasattr(data, 'dtype') and str(data.dtype).startswith('int'):
            maxv = float(np.iinfo(data.dtype).max) if np is not None else 32767.0
            data = data.astype('float32') / maxv
        if len(data.shape) > 1:
            data = data[:, 0]
        # naive resample if needed
        if sr != target_sr and np is not None:
            ratio = target_sr / sr
            new_len = int(len(data) * ratio)
            indices = np.linspace(0, len(data) - 1, new_len)
            data = np.interp(indices, np.arange(len(data)), data)
        return data.tolist() if not isinstance(data, list) else data
    except Exception:
        return None


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
    # normalize
    peak = max((abs(v) for v in out), default=1.0)
    if peak > 0:
        scale = gain / peak
        out = [v * scale for v in out]
    return out


class SampleMissingError(RuntimeError):
    pass


def render_audio(params: Dict[str, Any], midi: Dict[str, Any], samples: Dict[str, Any], log):
    instruments: List[str] = midi.get("meta", {}).get("instruments", [])
    log("func", "enter", {"module": "audio_renderer.py", "function": "render_audio", "params_keys": list(params.keys()), "samples_count": len(samples.get("samples", [])), "layers": len(instruments)})
    sr = params.get("sample_rate", 44100)
    seconds = params.get("seconds", 5.0)
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True, parents=True)
    frames = int(sr * seconds)
    wav_path = output_dir / "preview.wav"

    # Attempt sample-based rendering using layers
    layer_patterns: Dict[str, List[Dict[str, Any]]] = midi.get("layers", {})
    selected = samples.get("samples", [])
    sample_map: Dict[str, str] = {s.get("instrument"): s.get("file") for s in selected if s.get("instrument") and s.get("file")}

    log("audio", "render_start", {"sample_rate": sr, "seconds": seconds, "frames": frames, "module": "audio_renderer.py", "instruments": instruments, "samples": list(sample_map.keys())})

    tracks: List[List[float]] = []
    missing_instruments: List[str] = []
    for inst in instruments:
        pat = layer_patterns.get(inst)
        if not pat:
            continue
        file = sample_map.get(inst)
        buf: List[float] = [0.0] * frames
        base_wave: List[float] | None = None
        base_freq = 261.63  # assume C4 base
        if file and os.path.exists(file):
            base_wave = _load_wav_mono(file, sr)
            if base_wave is None:
                log("audio", "sample_load_failed", {"instrument": inst, "file": file})
                missing_instruments.append(inst)
        else:
            log("audio", "sample_missing", {"instrument": inst, "file": file})
            missing_instruments.append(inst)
        if base_wave is None:
            # Skip generating any audio for this instrument (strict mode)
            continue
        # place notes sequentially at positions derived from bar/step
        step_samples = int(sr * (seconds / max(1, len(pat) * 8)))  # rough time grid mapping
        for bar in pat:
            b = bar.get("bar", 0)
            for ev in bar.get("events", []):
                step = ev.get("step", 0)
                note = ev.get("note")
                vel = ev.get("vel", 100) / 127.0
                start = (b * 8 + step) * step_samples
                if start >= frames:
                    continue
                # build note audio
                target_freq = _note_freq(note)
                if base_wave is not None and np is not None:
                    pitched = _pitch_shift_resample(base_wave, base_freq, target_freq)
                    # apply amplitude and simple release
                    nl = min(len(pitched), frames - start)
                    if nl <= 0:
                        continue
                    # apply short ADSR
                    a = max(1, int(0.01 * sr))
                    r = max(1, int(0.1 * sr))
                    for i in range(nl):
                        amp = 1.0
                        if i < a:
                            amp = i / a
                        elif i > nl - r:
                            amp = max(0.0, (nl - i) / r)
                        v = pitched[i] * vel * amp
                        buf[start + i] += v
                else:
                    # Should not happen in strict mode (base_wave None handled early)
                    continue
        tracks.append(buf)
    if missing_instruments:
        raise SampleMissingError(f"Missing or failed samples for instruments: {', '.join(missing_instruments)}")
    if not tracks:
        raise SampleMissingError("No audio rendered: all instruments missing samples")

    # Mix and write
    mixed = _mix_tracks(tracks, gain=0.9)
    with wave.open(str(wav_path), 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        checkpoint = max(1, frames // 4)
        for i, v in enumerate(mixed):
            value = int(max(-1.0, min(1.0, v)) * 32767)
            wf.writeframes(struct.pack('<h', value))
            if i and i % checkpoint == 0:
                log("audio", "progress", {"written_frames": i, "percent": round(i/len(mixed)*100, 1)})
    size = wav_path.stat().st_size if wav_path.exists() else 0
    log("audio", "render_done", {"file": str(wav_path), "bytes": size, "mode": "samples"})
    result = {"audio_file": str(wav_path)}
    log("func", "exit", {"module": "audio_renderer.py", "function": "render_audio", "file": str(wav_path)})
    return result
