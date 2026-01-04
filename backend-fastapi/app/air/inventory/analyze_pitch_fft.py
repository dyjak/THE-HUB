from __future__ import annotations
from pathlib import Path
from typing import Iterable, Tuple, Optional
import json
import math
import wave
import contextlib

import numpy as np  # type: ignore

# ten moduł zawiera prostą analizę pitch (wysokości) dla plików wav.
#
# zastosowanie:
# - w trybie "deep" podczas budowy inventory próbujemy oszacować root_midi sampla
# - dzięki temu renderer może lepiej pitchować sample melodyczne (bliżej ich naturalnej wysokości)
#
# uwaga:
# - to jest heurystyka oparta o fft, nie pełna detekcja tonu (dla perkusji często zwróci None)


def _iter_wav_files(root: Path) -> Iterable[Path]:
    # iterator po wszystkich plikach wav w drzewie katalogów
    audio_exts = {".wav"}
    for f in root.rglob("*"):
        if f.is_file() and f.suffix.lower() in audio_exts:
            yield f


def _read_mono_segment(path: Path, max_seconds: float = 5.0) -> Tuple[np.ndarray, int]:
    """czyta do max_seconds sekund mono audio z wav jako tablicę float32.

    zasady:
    - jeśli plik jest stereo, bierzemy pierwszy kanał
    - jeśli plik jest krótszy niż max_seconds, czytamy całość
    - rzuca wyjątek dla nieprawidłowego/uszkodzonego wav
    """

    with contextlib.closing(wave.open(str(path), "rb")) as wf:
        sr = wf.getframerate()
        n_channels = wf.getnchannels()
        n_frames = wf.getnframes()
        max_frames = n_frames
        if max_seconds > 0 and sr > 0:
            max_frames = min(n_frames, int(sr * max_seconds))
        frames = wf.readframes(max_frames)
        sampwidth = wf.getsampwidth()
        if sampwidth != 2:
            raise ValueError(f"Unsupported sample width: {sampwidth}")
        import struct

        total_samples = max_frames * n_channels
        fmt = "<" + "h" * total_samples
        ints = struct.unpack(fmt, frames)
        if n_channels > 1:
            ints = ints[0::n_channels]
        data = np.asarray(ints, dtype="float32") / 32768.0
        return data, sr


_NOTE_NAMES_SHARP = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def _freq_to_midi(freq: float) -> Optional[float]:
    if freq <= 0:
        return None
    return 69 + 12.0 * math.log2(freq / 440.0)


def _midi_to_name(midi: float) -> str:
    n = int(round(midi))
    note = n % 12
    octave = n // 12 - 1
    return f"{_NOTE_NAMES_SHARP[note]}{octave}"


def estimate_root_pitch(path: Path) -> Optional[dict]:
    """szacuje dominującą wysokość dźwięku w pliku wav prostą metodą fft.

    zwraca dict z polami: pitch_hz, pitch_midi, pitch_name, confidence.
    zwraca None, jeśli estymacja się nie uda (np. plik za krótki, cisza, mocno perkusyjny charakter).
    """

    try:
        data, sr = _read_mono_segment(path)
    except Exception:
        return None

    if sr <= 0 or data.size == 0:
        return None

    # okno hann'a zmniejsza "przeciekanie" widma (spectral leakage)
    n = data.size
    if n < 1024:
        return None
    window = np.hanning(n).astype("float32")
    windowed = data * window

    # fft i moduł widma
    spec = np.fft.rfft(windowed)
    mag = np.abs(spec)

    # oś częstotliwości
    freqs = np.fft.rfftfreq(n, d=1.0 / sr)

    # ignorujemy skrajnie niskie i wysokie pasmo (poniżej 30 hz, powyżej 5 khz)
    lo = np.searchsorted(freqs, 30.0)
    hi = np.searchsorted(freqs, 5000.0)
    mag = mag[lo:hi]
    freqs = freqs[lo:hi]
    if mag.size == 0:
        return None

    # znajdujemy najwyższy pik widma
    idx = int(np.argmax(mag))
    peak_freq = float(freqs[idx])
    peak_mag = float(mag[idx])

    # prosta "pewność": stosunek piku do mediany energii widma
    median_mag = float(np.median(mag)) or 1e-9
    confidence = peak_mag / median_mag

    midi = _freq_to_midi(peak_freq)
    if midi is None:
        return None
    name = _midi_to_name(midi)

    return {
        "pitch_hz": peak_freq,
        "pitch_midi": midi,
        "pitch_name": name,
        "confidence": confidence,
    }


def main() -> None:
    # import lokalny, żeby uniknąć cyklicznego importu (inventory importuje analyze_pitch_fft).
    # użycie jako skrypt cli nadal działa.
    from .inventory import DEFAULT_LOCAL_SAMPLES_ROOT  # type: ignore

    root = DEFAULT_LOCAL_SAMPLES_ROOT
    results = []
    for wav_path in _iter_wav_files(root):
        est = estimate_root_pitch(wav_path)
        if not est:
            continue
        rel = wav_path.relative_to(root)
        row = {
            "file_rel": rel.as_posix(),
            "file_abs": str(wav_path.resolve()),
            **est,
        }
        results.append(row)
        print(f"{row['file_rel']}: {row['pitch_name']} ({row['pitch_hz']:.1f} Hz, conf={row['confidence']:.1f})")

    out_path = Path(__file__).parent / "pitch_analysis.json"
    try:
        out_path.write_text(json.dumps({"root": str(root), "results": results}, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


if __name__ == "__main__":
    main()
