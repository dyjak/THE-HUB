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
# log.setLevel(logging.DEBUG)
# if not logging.getLogger().handlers:
#     logging.basicConfig(level=logging.DEBUG)

# Base reference frequency for pitch-shifting (assume C4 for raw samples),
# kept in sync conceptually with the experimental audio_renderer.
_BASE_FREQ = 261.63 # C4
#_BASE_FREQ = 523.25  # C5


def _note_freq(midi_note: int) -> float:
    return 440.0 * (2 ** ((midi_note - 69) / 12.0))


def _freq_to_midi(freq: float) -> Optional[int]:
    """Approximate MIDI note number from frequency.

    Returns None for non-positive frequencies.
    """

    if freq <= 0.0:
        return None
    return int(round(69 + 12 * math.log(freq / 440.0, 2.0)))


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


def _clamp_note_near_base(base_midi: int, target_midi: int, max_semitones: int) -> int:
    """Clamp target_midi to stay within a window around base_midi.

    This keeps a given sample playing roughly in its natural register
    while preserving the direction and relative size of MIDI intervals.
    """

    if max_semitones <= 0:
        return target_midi
    lo = base_midi - max_semitones
    hi = base_midi + max_semitones
    if target_midi < lo:
        return lo
    if target_midi > hi:
        return hi
    return target_midi


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


def _pitch_shift_resample(samples: List[float], base_freq: float, target_freq: float, max_semitones: float | None = None) -> List[float]:
    """Simple resampling pitch-shift using numpy if available.

    If numpy is missing or base_freq invalid, returns the original samples.

    Optional max_semitones clamps the pitch shift range around base_freq,
    which helps avoid extremely unnatural transpositions (e.g. many octaves).
    """

    try:
        import numpy as np  # type: ignore
    except Exception:  # pragma: no cover - environments without numpy
        return samples

    if base_freq <= 0.0:
        return samples

    # Clamp pitch shift in semitones if requested.
    if max_semitones is not None and max_semitones > 0.0:
        try:
            # ratio = target / base, semitones = 12 * log2(ratio)
            raw_ratio = target_freq / base_freq
            if raw_ratio <= 0.0:
                return samples
            semitones = 12.0 * math.log(raw_ratio, 2.0)
            if semitones > max_semitones:
                semitones = max_semitones
            elif semitones < -max_semitones:
                semitones = -max_semitones
            ratio = 2.0 ** (semitones / 12.0)
            target_freq = base_freq * ratio
        except Exception:
            ratio = target_freq / base_freq
    else:
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


def recommend_sample_for_instrument(
    instrument: str,
    lib: Dict[str, List[LocalSample]],
    midi_layers: Dict[str, Any] | None,
) -> LocalSample | None:
    """Zaproponuj LocalSample na podstawie MIDI + inventory.

    Strategia:
    - zbierz wszystkie nuty MIDI dla danego instrumentu,
    - policz medianę wysokości (median_note),
    - wybierz sample z inventory, którego root_midi jest możliwie najbliżej
      median_note.

    Funkcja jest czysto doradcza: NIE nadpisuje niczego w renderze sama z siebie,
    tylko zwraca referencję do próbki. Frontend może tę rekomendację zapisać
    w param JSON jako selected_samples[instrument].
    """

    rows = lib.get(instrument) or []
    if not rows or not isinstance(midi_layers, dict):
        return None

    # Zbieramy wszystkie nuty z warstwy MIDI dla danego instrumentu.
    notes: List[int] = []
    layer = midi_layers.get(instrument) or []
    for bar in layer:
        for ev in (bar.get("events") or []):
            n = ev.get("note")
            if isinstance(n, int):
                notes.append(n)
    if not notes:
        return None

    notes_sorted = sorted(notes)
    mid = len(notes_sorted) // 2
    if len(notes_sorted) % 2 == 1:
        median_note = float(notes_sorted[mid])
    else:
        median_note = (notes_sorted[mid - 1] + notes_sorted[mid]) / 2.0

    best: LocalSample | None = None
    best_dist: float | None = None
    for s in rows:
        try:
            if s.root_midi is None:
                continue
            dist = abs(float(s.root_midi) - median_note)
            if best is None or best_dist is None or dist < best_dist:
                if s.file.exists():
                    best = s
                    best_dist = dist
        except Exception:
            continue

    if best is not None:
        log.debug(
            "[sample-select] instrument=%s strategy=median_midi median_note=%.2f root_midi=%s sample_id=%s path=%s",
            instrument,
            median_note,
            best.root_midi,
            best.id,
            best.file,
        )
    return best


def _resolve_sample_for_instrument(
    instrument: str,
    selected_samples: Dict[str, str] | None,
    lib: Dict[str, List[LocalSample]],
) -> LocalSample | None:
    """Find the LocalSample for an instrument using selected_samples + inventory.

    Tu NIE stosujemy automatycznej heurystyki – renderer respektuje tylko to,
    co przyszło z frontendu (selected_samples), a jeśli brak wyboru, spada
    do prostego fallbacku: pierwsza dostępna próbka.
    Inteligentne dobieranie sampli dzieje się wcześniej, na żądanie UI
    (np. przez osobny endpoint, który wywołuje recommend_sample_for_instrument
    i zwraca gotowe sample_id do zapisania w param JSON).
    """

    # 1) Frontend override – jeśli użytkownik coś wybrał, szanujemy ten wybór.
    sample_id = (selected_samples or {}).get(instrument)
    if sample_id:
        s = find_sample_by_id(lib, instrument, sample_id)
        if s and s.file.exists():
            return s

    # 2) Fallback: pierwsza dostępna próbka (obecne zachowanie).
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
        sample = _resolve_sample_for_instrument(
            instrument,
            req.selected_samples,
            lib,
        )
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

        # Historycznie MIDI z generatora miało pierwszy takt ustawiony na 1,
        # co powodowało kilka sekund ciszy na początku renderu.
        # Zamiast przesuwać cały pattern do lewej (min_bar), odejmujemy
        # tylko "jednostkowe" przesunięcie, jeśli pierwszy bar to dokładnie 1.
        min_bar = 0
        try:
            if layer:
                raw_min_bar = min(int(b.get("bar", 0)) for b in layer)
                min_bar = 1 if raw_min_bar == 1 else 0
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
        base_midi: Optional[int] = None
        try:
            rm = getattr(sample, "root_midi", None)
            if rm is not None:
                base_midi = int(round(float(rm)))
                base_freq = _note_freq(base_midi)
        except Exception:
            base_freq = _BASE_FREQ
            base_midi = None
        if base_midi is None:
            # Approximate MIDI from fallback base frequency so that
            # melodic mapping still behaves reasonably.
            base_midi = _freq_to_midi(base_freq) or 60
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
                        #
                        # Uniwersalny mechanizm pitchowania melodii:
                        #
                        # 1) Nutę docelową bierzemy wprost z MIDI (target_midi),
                        #    dzięki czemu zachowujemy matematycznie poprawną tonację
                        #    w całym utworze.
                        # 2) Nie "przyciskamy" target_midi do sztywnego okna
                        #    wokół base_midi (brak twardego clampa na samą nutę),
                        #    żeby uniknąć sytuacji w której wiele odległych nut
                        #    brzmi jak jedna i ta sama wysokość.
                        # 3) Zamiast tego liczymy różnicę w półtonach względem
                        #    naturalnego rejestru sampla (base_midi) i tę różnicę
                        #    miękko kompresujemy funkcją tanh. Małe interwały
                        #    (typowo używane w muzyce) przechodzą praktycznie
                        #    bez zmian, natomiast bardzo duże skoki są coraz
                        #    silniej "spłaszczane" do rozsądnego zakresu.
                        #
                        #    raw_semi = target_midi - base_midi
                        #    x        = raw_semi / max_semi
                        #    compressed = tanh(x) * max_semi
                        #
                        #    Dla |raw_semi| << max_semi => tanh(x) ~ x,
                        #    więc compressed ~ raw_semi (dokładne pitchowanie
                        #    jak w MIDI, zachowane interwały).
                        #    Dla bardzo dużych |raw_semi| => tanh(x) -> ±1,
                        #    więc compressed zbliża się gładko do ±max_semi,
                        #    dzięki czemu sample nigdy nie odlatuje o wiele
                        #    oktaw od swojego naturalnego rejestru, ale jednocześnie
                        #    każda różna nuta dostaje inną (choć coraz mniej różną)
                        #    wysokość.
                        #
                        # 4) Ograniczamy w ten sposób "siłę" pitch-shiftu (ratio)
                        #    zamiast brutalnie korygować nutę. To daje efekt,
                        #    który jest jednocześnie muzycznie spójny, zgodny z MIDI
                        #    i odporny na ekstremalne przypadki (wysokie / niskie
                        #    dźwięki, nietypowe base_freq w samplach).

                        target_midi = int(note)

                        # interwał względem naturalnego rejestru sampla
                        raw_semi = target_midi - base_midi

                        # Maksymalny "efektywny" zakres, w którym pitch-shift
                        # może się jeszcze rozciągać liniowo. Poza nim
                        # interwał jest coraz mocniej kompresowany.
                        #
                        # Ustawiamy ten zakres per-instrument, żeby:
                        # - dla basów ograniczyć transpozycję (brzmienie szybko
                        #   robi się nienaturalne w skrajnych rejestrach),
                        # - dla instrumentów harmonicznych / leadowych (piano,
                        #   pads, strings, sax, itp.) pozwolić na większy
                        #   zakres pracy, tak aby wyższe nuty faktycznie
                        #   różniły się wysokością, a nie były "przyklejone"
                        #   do sufitu tanh.
                        instrument_max_semi = {
                            "bass": 7,
                            "bass guitar": 7,
                            "piano": 24,
                            "pads": 24,
                            "strings": 24,
                            "sax": 24,
                            "acoustic guitar": 24,
                            "electric guitar": 24,
                        }
                        max_semi = instrument_max_semi.get(key, 18)

                        if max_semi > 0:
                            x = raw_semi / float(max_semi)
                            compressed = math.tanh(x) * float(max_semi)
                        else:
                            compressed = 0.0

                        # Z powrotem do współczynnika częstotliwości (ratio).
                        ratio = 2.0 ** (compressed / 12.0)
                        target_freq_eff = base_freq * ratio

                        log.debug(
                            "[pitch] inst=%s note=%s base_midi=%s raw_semi=%s "
                            "compressed=%.3f ratio=%.4f base_freq=%.2f target_freq=%.2f",
                            instrument,
                            note,
                            base_midi,
                            raw_semi,
                            compressed,
                            ratio,
                            base_freq,
                            target_freq_eff,
                        )

                        pitched = _pitch_shift_resample(
                            base_wave,
                            base_freq,
                            target_freq_eff,
                            max_semitones=None,
                        )
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
