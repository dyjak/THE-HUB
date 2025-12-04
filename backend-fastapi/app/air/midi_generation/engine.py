from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import json
from datetime import datetime

try:  # opcjonalny export .mid
    import mido  # type: ignore
except Exception:  # pragma: no cover - środowiska bez mido
    mido = None  # type: ignore

#from app.tests.ai_render_test.debug_store import DEBUG_STORE  # TODO: zastąpić własnym store jeśli potrzebne


BASE_OUTPUT_DIR = Path(__file__).parent / "output"
BASE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

#debug
class _DummyRun:
    def __init__(self) -> None:
        from uuid import uuid4
        self.run_id = str(uuid4())

    def log(self, category: str, event: str, payload: dict) -> None:
        # Możesz tu w razie czego zrobić print/logowanie do pliku
        pass
class _DummyStore:
    def start(self) -> "_DummyRun":
        return _DummyRun()
DEBUG_STORE = _DummyStore()


def _safe_parse_midi_json(raw: str) -> Tuple[Dict[str, Any], List[str]]:
    """Minimalny parser JSON z delikatnym odzyskiwaniem (analogiczny do _safe_parse_json).

    Zdejmuje ewentualne ``` fences i próbuje przyciąć do ostatniej klamry.
    """

    errors: List[str] = []
    text = (raw or "").strip()
    if text.startswith("```"):
        try:
            fence_end = text.index("```", 3) + 3
            tail = text[fence_end:]
            if "```" in tail:
                inner_end = tail.rindex("```")
                text = tail[:inner_end].strip()
            else:
                text = tail.strip()
        except ValueError:
            errors.append("parse: unable to strip markdown fences")
    last_error: Optional[Exception] = None
    for attempt in range(2):
        try:
            obj = json.loads(text)
            if isinstance(obj, dict):
                return obj, errors
            errors.append("parse: top-level JSON must be object")
            return {}, errors
        except Exception as e:  # noqa: PERF203
            last_error = e
            if attempt == 0:
                last_brace = text.rfind("}")
                if last_brace > 0:
                    text = text[: last_brace + 1]
                    errors.append(f"parse: truncated to last brace due to {e}")
                    continue
            errors.append(f"parse: {e}")
            break
    return {}, errors


def _ensure_midi_structure(meta: Dict[str, Any], midi_data: Dict[str, Any]) -> Dict[str, Any]:
    """Zapewnia, że midi_data ma pattern/layers/meta w podstawowej formie.

    Jeśli model zwróci tylko layers bez pattern, zbudujemy pattern jako sumę.
    Jeśli nie ma meta, uzupełnimy z wejściowego meta (tempo, instruments itd.).
    """

    if not isinstance(midi_data, dict):
        midi_data = {}
    midi_meta = midi_data.setdefault("meta", {}) if isinstance(midi_data, dict) else {}
    for k in (
        "tempo","key","scale","style","mood","meter","form",
        "dynamic_profile","arrangement_density","harmonic_color",
        "length_seconds","bars","instrument_configs","seed",
    ):
        if k in meta and meta.get(k) is not None:
            midi_meta.setdefault(k, meta.get(k))
    midi_meta.setdefault("instruments", meta.get("instruments"))

    layers = midi_data.get("layers")
    if not isinstance(layers, dict):
        layers = {}
        midi_data["layers"] = layers
    pattern = midi_data.get("pattern")
    if not isinstance(pattern, list):
        pattern = _build_pattern_from_layers(layers)
        midi_data["pattern"] = pattern
    return midi_data


def _build_pattern_from_layers(layers: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Buduje pattern jako sumę wszystkich warstw.

    Wspólna funkcja, której użyjemy również do generowania patternów
    per-instrument.
    """

    combined: Dict[int, Dict[str, Any]] = {}
    for _, pat in (layers or {}).items():
        if not isinstance(pat, list):
            continue
        for bar in pat:
            try:
                b = int(bar.get("bar", 0))
            except Exception:
                b = 0
            dst = combined.setdefault(b, {"bar": b, "events": []})
            dst.setdefault("events", [])
            dst["events"].extend(bar.get("events", []) or [])
    if not combined:
        return []
    return [combined[i] for i in sorted(combined.keys())]


def _export_pattern_to_mid(pattern: List[Dict[str, Any]], tempo_bpm: int, out_path: Path) -> Optional[Path]:
    """Eksportuje prosty pattern do pliku .mid (jak w module testowym)."""

    if mido is None:
        return None
    mid = mido.MidiFile()
    track = mido.MidiTrack()
    mid.tracks.append(track)
    mpb = int(60_000_000 / max(1, tempo_bpm))
    track.append(mido.MetaMessage("set_tempo", tempo=mpb, time=0))
    ticks_per_beat = mid.ticks_per_beat
    step_ticks = int(ticks_per_beat * 0.5)
    flat: List[tuple[int, bool, int, int]] = []
    for bar in pattern:
        b_index = int(bar.get("bar", 0) or 0)
        for ev in bar.get("events", []) or []:
            note = int(ev.get("note", 60) or 60)
            vel = int(ev.get("vel", 64) or 64)
            step = int(ev.get("step", 0) or 0)
            start_tick = (b_index * 8 + step) * step_ticks
            length_steps = int(ev.get("len", 1) or 1)
            end_tick = start_tick + length_steps * step_ticks
            flat.append((start_tick, True, note, vel))
            flat.append((end_tick, False, note, vel))
    flat.sort(key=lambda x: x[0])
    current_tick = 0
    for tick, is_on, note, vel in flat:
        delta = tick - current_tick
        current_tick = tick
        if is_on:
            track.append(mido.Message("note_on", note=note, velocity=vel, time=delta))
        else:
            track.append(mido.Message("note_off", note=note, velocity=0, time=delta))
    mid.save(str(out_path))
    return out_path


def _render_pianoroll_svg(midi_data: Dict[str, Any], out_path: Path) -> Optional[Path]:
    """Generuje prosty pianoroll jako SVG (bars x 8 stepów, oś nut).

    To jest wersja robocza – bez skalowania do pikseli perfect.
    """

    pattern = midi_data.get("pattern") or []
    if not isinstance(pattern, list) or not pattern:
        return None
    notes: List[int] = []
    for bar in pattern:
        for ev in bar.get("events", []) or []:
            n = ev.get("note")
            if isinstance(n, int):
                notes.append(n)
    if not notes:
        return None
    min_note = min(notes)
    max_note = max(notes)
    pitch_range = max(1, max_note - min_note + 1)
    bar_count = len(pattern)
    steps_per_bar = 8

    # prosty grid: każdy step = 20 px, każda nuta = 6 px height
    step_w = 20
    note_h = 6
    padding = 10
    width = padding * 2 + bar_count * steps_per_bar * step_w
    height = padding * 2 + pitch_range * note_h

    def note_to_y(n: int) -> int:
        idx = max_note - n  # wyższe nuty wyżej
        return padding + idx * note_h

    svg_parts: List[str] = []
    svg_parts.append(f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}'>")
    svg_parts.append("<rect x='0' y='0' width='100%' height='100%' fill='black' />")

    # pionowe linie taktów
    for b in range(bar_count + 1):
        x = padding + b * steps_per_bar * step_w
        svg_parts.append(f"<line x1='{x}' y1='{padding}' x2='{x}' y2='{height-padding}' stroke='rgba(255,255,255,0.25)' stroke-width='1' />")

    # poziome linie co oktawę (~12 półtonów)
    for p in range(min_note, max_note + 1):
        if (p - min_note) % 12 == 0:
            y = note_to_y(p)
            svg_parts.append(f"<line x1='{padding}' y1='{y}' x2='{width-padding}' y2='{y}' stroke='rgba(255,255,255,0.25)' stroke-width='1' />")

    # nuty jako prostokąty
    for bar in pattern:
        b_index = int(bar.get("bar", 0) or 0)
        for ev in bar.get("events", []) or []:
            try:
                step = int(ev.get("step", 0) or 0)
                length_steps = int(ev.get("len", 1) or 1)
                note = int(ev.get("note", 60) or 60)
                vel = int(ev.get("vel", 80) or 80)
            except Exception:
                continue
            x = padding + (b_index * steps_per_bar + step) * step_w
            y = note_to_y(note)
            w = max(4, length_steps * step_w)
            # jasność od velocity
            alpha = min(1.0, 0.3 + (vel / 127.0) * 0.7)
            svg_parts.append(f"<rect x='{x}' y='{y}' width='{w}' height='{note_h-1}' fill='rgba(0,255,128,{alpha:.2f})' rx='1' ry='1' />")

    svg_parts.append("</svg>")
    out_path.write_text("\n".join(svg_parts), encoding="utf-8")
    return out_path


def generate_midi_and_artifacts(
    meta: Dict[str, Any], midi_data: Dict[str, Any]
) -> Tuple[
    str,
    Dict[str, Any],
    Dict[str, Optional[str]],
    Dict[str, Dict[str, Any]],
    Dict[str, Dict[str, Optional[str]]],
]:
    """Główna funkcja silnika: porządkuje strukturę MIDI i generuje artefakty.

    Zwraca:
    - run_id,
    - midi_data (globalny plan),
    - artifacts (globalne artefakty),
    - midi_per_instrument (strukturya MIDI per instrument),
    - artifacts_per_instrument (artefakty per instrument).
    """

    run = DEBUG_STORE.start()
    run.log("run", "midi_generation", {"source": "midi_generation_module"})

    midi_data = _ensure_midi_structure(meta, midi_data)

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    run_dir = BASE_OUTPUT_DIR / f"{ts}_{run.run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)

    midi_json_path = run_dir / "midi.json"
    with midi_json_path.open("w", encoding="utf-8") as f:
        json.dump(midi_data, f)
    run.log("midi", "saved_json", {"file": str(midi_json_path)})

    midi_mid_path: Optional[Path] = None
    tempo = int(midi_data.get("meta", {}).get("tempo", meta.get("tempo", 80)))
    if mido is not None:
        try:
            midi_mid_path = _export_pattern_to_mid(midi_data.get("pattern") or [], tempo, run_dir / "midi.mid")
            if midi_mid_path:
                run.log("midi", "export_mid", {"file": str(midi_mid_path)})
        except Exception as e:
            run.log("midi", "export_mid_failed", {"error": str(e)})

    midi_svg_path: Optional[Path] = None
    try:
        midi_svg_path = _render_pianoroll_svg(midi_data, run_dir / "pianoroll.svg")
        if midi_svg_path:
            run.log("viz", "pianoroll_svg", {"file": str(midi_svg_path)})
    except Exception as e:
        run.log("viz", "pianoroll_svg_failed", {"error": str(e)})

    def _rel(p: Optional[Path]) -> Optional[str]:
        if p is None:
            return None
        try:
            return str(p.relative_to(BASE_OUTPUT_DIR))
        except Exception:
            return p.name

    artifacts = {
        "midi_json_rel": _rel(midi_json_path),
        "midi_mid_rel": _rel(midi_mid_path) if midi_mid_path else None,
        "midi_image_rel": _rel(midi_svg_path) if midi_svg_path else None,
    }

    # --- Nowość: podział MIDI per instrument ---
    midi_per_instrument: Dict[str, Dict[str, Any]] = {}
    artifacts_per_instrument: Dict[str, Dict[str, Optional[str]]] = {}

    layers = midi_data.get("layers") or {}
    if isinstance(layers, dict):
        for inst, inst_layer in layers.items():
            # Zbuduj strukturę MIDI tylko dla danego instrumentu.
            inst_layers = {inst: inst_layer} if isinstance(inst_layer, list) else {}
            inst_pattern = _build_pattern_from_layers(inst_layers)

            inst_meta = dict(midi_data.get("meta") or {})
            inst_meta["instrument"] = inst

            inst_midi: Dict[str, Any] = {
                "meta": inst_meta,
                "layers": inst_layers,
                "pattern": inst_pattern,
            }
            midi_per_instrument[inst] = inst_midi

            # Artefakty na dysku
            safe_inst = str(inst).replace("/", "_").replace("\\", "_")
            inst_json_path = run_dir / f"midi_{safe_inst}.json"
            with inst_json_path.open("w", encoding="utf-8") as f:
                json.dump(inst_midi, f)
            run.log("midi", "saved_json_instrument", {"instrument": inst, "file": str(inst_json_path)})

            inst_mid_path: Optional[Path] = None
            try:
                if mido is not None:
                    inst_mid_path = _export_pattern_to_mid(inst_pattern, tempo, run_dir / f"midi_{safe_inst}.mid")
                    if inst_mid_path:
                        run.log("midi", "export_mid_instrument", {"instrument": inst, "file": str(inst_mid_path)})
            except Exception as e:
                run.log("midi", "export_mid_instrument_failed", {"instrument": inst, "error": str(e)})

            inst_svg_path: Optional[Path] = None
            try:
                inst_svg_path = _render_pianoroll_svg(inst_midi, run_dir / f"pianoroll_{safe_inst}.svg")
                if inst_svg_path:
                    run.log("viz", "pianoroll_svg_instrument", {"instrument": inst, "file": str(inst_svg_path)})
            except Exception as e:
                run.log("viz", "pianoroll_svg_instrument_failed", {"instrument": inst, "error": str(e)})

            artifacts_per_instrument[inst] = {
                "midi_json_rel": _rel(inst_json_path),
                "midi_mid_rel": _rel(inst_mid_path) if inst_mid_path else None,
                "midi_image_rel": _rel(inst_svg_path) if inst_svg_path else None,
            }

    # Zapisujemy zbiorczy opis podziału per instrument w jednym JSON-ie ułatwiającym
    # późniejsze testowe pipeline'y (np. mini_pipeline_test).
    try:
        per_inst_path = run_dir / "midi_per_instrument.json"
        with per_inst_path.open("w", encoding="utf-8") as f:
            json.dump(midi_per_instrument, f)
        run.log("midi", "saved_midi_per_instrument_index", {"file": str(per_inst_path)})
    except Exception as e:
        run.log("midi", "save_midi_per_instrument_index_failed", {"error": str(e)})

    run.log("run", "completed", {"midi_json_rel": artifacts["midi_json_rel"]})
    return run.run_id, midi_data, artifacts, midi_per_instrument, artifacts_per_instrument
