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
    try:
        import scipy.io.wavfile as wavfile  # type: ignore
        sr, data = wavfile.read(str(path))
        if len(data.shape) > 1:
            data = data[:,0]
        if hasattr(data, 'dtype'):
            import numpy as np  # type: ignore
            maxv = float(np.iinfo(data.dtype).max)
            data = data.astype('float32')/maxv
        return data.tolist()
    except Exception:
        return None

BASE_FREQ = 261.63  # assume C4 for raw samples


def render_audio(audio_params: Dict[str, Any], midi: Dict[str, Any], samples: Dict[str, Any], log):
    sr = audio_params.get("sample_rate", 44100)
    seconds = audio_params.get("seconds", 5.0)
    frames = int(sr * seconds)
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    wav_path = output_dir / "preview.wav"
    instruments: List[str] = midi.get("meta", {}).get("instruments", [])
    sample_map: Dict[str, str] = {s.get("instrument"): s.get("file") for s in samples.get("samples", [])}
    log("audio", "render_start", {"instruments": instruments, "sample_count": len(sample_map)})
    tracks: List[List[float]] = []
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
        tracks.append(buf)
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
    return {"audio_file": str(wav_path)}
