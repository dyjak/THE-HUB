from __future__ import annotations
from typing import Dict, Any
import math
import wave
import struct
from pathlib import Path


def render_audio(params: Dict[str, Any], midi: Dict[str, Any], samples: Dict[str, Any], log):
    log("func", "enter", {"module": "audio_renderer.py", "function": "render_audio", "params_keys": list(params.keys()), "samples_count": len(samples.get("samples", []))})
    sr = params.get("sample_rate", 44100)
    seconds = params.get("seconds", 5.0)
    freq = 220.0
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True, parents=True)
    frames = int(sr * seconds)
    wav_path = output_dir / "preview.wav"

    log("audio", "render_start", {"sample_rate": sr, "seconds": seconds, "frames": frames, "module": "audio_renderer.py"})
    with wave.open(str(wav_path), 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        checkpoint = max(1, frames // 4)
        for i in range(frames):
            # prosty sin jako placeholder
            value = int(32767 * math.sin(2 * math.pi * freq * (i / sr)))
            wf.writeframes(struct.pack('<h', value))
            if i and i % checkpoint == 0:
                log("audio", "progress", {"written_frames": i, "percent": round(i/frames*100, 1)})
    size = wav_path.stat().st_size if wav_path.exists() else 0
    log("audio", "render_done", {"file": str(wav_path), "bytes": size})
    result = {"audio_file": str(wav_path)}
    log("func", "exit", {"module": "audio_renderer.py", "function": "render_audio", "file": str(wav_path)})
    return result
