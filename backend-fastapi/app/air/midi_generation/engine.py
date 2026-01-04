from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import json
from datetime import datetime
from uuid import uuid4

# ten moduł jest "silnikiem" kroku midi_generation.
#
# odpowiedzialność:
# - przyjąć wynik wygenerowany przez llm (zwykle json z `pattern` i/lub `layers`)
# - doprowadzić strukturę do spójnej postaci (uzupełnić meta, zbudować pattern z layers, itp.)
# - zapisać artefakty na dysku w katalogu output (json, opcjonalnie .mid, podgląd svg)
# - opcjonalnie wygenerować dodatkowe pliki "per instrument", żeby ui mogło pokazywać rozbicie śladów
#
# ważne pojęcia:
# - `pattern`: lista taktów, gdzie każdy takt ma listę eventów (step/note/vel/len)
#   używane głównie do perkusji (wspólny kanał zdarzeń)
# - `layers`: słownik instrument -> pattern, używany głównie do instrumentów melodycznych
# - "best-effort": jeśli coś się nie uda (np. svg albo mid), nie przerywamy całej generacji

try:  # opcjonalny export .mid
    import mido  # type: ignore
except Exception:  # pragma: no cover - środowiska bez mido
    mido = None  # type: ignore

# w tym module nie używamy debug_store z innych kroków.
# run_id generujemy lokalnie i zapisujemy artefakty do katalogu z timestampem.


BASE_OUTPUT_DIR = Path(__file__).parent / "output"
BASE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _canon_inst_name(name: Any) -> str:
    # normalizuje nazwę instrumentu do postaci porównywalnej (lowercase, pojedyncze spacje)
    return " ".join(str(name or "").strip().lower().split())


def _notes_for_percussion_instrument(name: str) -> Optional[List[int]]:
    """mapuje popularne nazwy elementów perkusji na numery nut general midi.

    ważne:
    - nazwy bywają niejednoznaczne (np. "hat"), więc dla hi-hatu akceptujemy zarówno
      zamknięty (42), jak i otwarty (46), żeby eventy z obu wariantów dało się przypisać.
    """

    n = _canon_inst_name(name)
    direct: Dict[str, List[int]] = {
        # Core kit
        "kick": [36],
        "snare": [38],
        # Additional common kit pieces
        "clap": [39],
        "rim": [37],
        "rimshot": [37],
        "side stick": [37],
        "hat": [42, 46],
        "hihat": [42, 46],
        "hi hat": [42, 46],
        "closed hat": [42],
        "open hat": [46],
        "crash": [49],
        "ride": [51],
        "splash": [55],
        "shake": [82],
        "shaker": [82],
        # 808: keep distinct from kick (36) by using 35 by default.
        "808": [35],
        "low tom": [45],
        "mid tom": [47],
        "high tom": [50],
        "tom": [45, 47, 50],
    }
    if n in direct:
        return direct[n]
    # light heuristics
    if "hat" in n:
        return [42, 46]
    if "clap" in n:
        return [39]
    if "rim" in n or "side" in n:
        return [37]
    if "crash" in n:
        return [49]
    if "ride" in n:
        return [51]
    if "splash" in n:
        return [55]
    if "shake" in n or "shaker" in n:
        return [82]
    if "tom" in n:
        return [45, 47, 50]
    return None


def _filter_pattern_by_notes(pattern: List[Dict[str, Any]], allowed_notes: List[int], bars: int | None = None) -> List[Dict[str, Any]]:
    # filtruje pattern i zostawia tylko eventy, których `note` należy do `allowed_notes`.
    # używane przy rozbijaniu perkusji (globalny pattern) na osobne instrumenty.
    allowed = set(int(x) for x in (allowed_notes or []) if isinstance(x, int) or str(x).isdigit())
    if not allowed:
        return []

    out: List[Dict[str, Any]] = []
    for bar in (pattern or []):
        try:
            b = int(bar.get("bar", 0) or 0)
        except Exception:
            b = 0
        evs: List[Dict[str, Any]] = []
        for ev in bar.get("events", []) or []:
            try:
                note = int(ev.get("note", -1))
            except Exception:
                continue
            if note in allowed:
                evs.append(ev)
        if evs:
            out.append({"bar": b, "events": evs})

    # opcjonalnie normalizujemy zakres taktów (1..bars), żeby ui miało stabilny widok
    if bars and bars > 0:
        existing = {int(b.get("bar", 0) or 0): b for b in out}
        normalized: List[Dict[str, Any]] = []
        for i in range(1, bars + 1):
            normalized.append(existing.get(i, {"bar": i, "events": []}))
        return normalized

    return out

# poniżej jest stary, zakomentowany szkic "dummy" loggera.
# zostawiamy go jako kontekst historyczny, ale w produkcyjnym przepływie nie jest używany.


def _safe_parse_midi_json(raw: str) -> Tuple[Dict[str, Any], List[str]]:
    """minimalny parser json z delikatnym odzyskiwaniem.

    po co to jest:
    - llm czasem zwraca ```json ... ``` mimo że prosimy o "sam json"
    - odpowiedź bywa ucięta i wtedy pomaga przycięcie do ostatniej `}`

    zwraca:
    - sparsowany obiekt (lub pusty dict)
    - listę błędów/ostrzeżeń opisujących, co poszło nie tak
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
    """upewnia się, że `midi_data` ma podstawową, spójną strukturę.

    co dokładnie robimy:
    - jeśli w odpowiedzi nie ma `meta`, to uzupełniamy je danymi wejściowymi (tempo, bars, instrumenty itd.)
    - jeśli w odpowiedzi nie ma `layers`, tworzymy pusty słownik
    - jeśli w odpowiedzi nie ma `pattern`, budujemy go jako "sumę" eventów ze wszystkich warstw
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
    """buduje globalny `pattern` jako sumę eventów ze wszystkich warstw (`layers`).

    dlaczego to jest potrzebne:
    - czasem llm zwraca tylko `layers` (np. dla instrumentów melodycznych)
    - ui/render łatwiej obsługują też ustandaryzowany `pattern`, więc go dopinamy
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
    """eksportuje prosty pattern do pliku .mid.

    uwagi:
    - ten eksport jest bardzo podstawowy (siatka 8 kroków na takt)
    - jeśli biblioteka `mido` nie jest dostępna, funkcja zwraca `None`
    """

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
    """generuje prosty podgląd pianoroll jako svg.

    jak to działa w skrócie:
    - oś x: takty * 8 kroków na takt
    - oś y: wysokość nut (min..max z eventów)
    - prostokąty reprezentują nuty, a jasność zależy od velocity

    to jest wersja robocza (bez perfekcyjnego skalowania i bez opisów osi).
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
    """główna funkcja silnika: porządkuje strukturę midi i generuje artefakty.

    zwraca:
    - run_id: krótki identyfikator uruchomienia
    - midi_data: globalny plan midi (meta + layers + pattern)
    - artifacts: ścieżki względne do plików globalnych (json/mid/svg)
    - midi_per_instrument: osobne struktury midi dla instrumentów (jeśli uda się je przygotować)
    - artifacts_per_instrument: ścieżki do plików per instrument
    """

    run_id = uuid4().hex[:12]

    midi_data = _ensure_midi_structure(meta, midi_data)

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    run_dir = BASE_OUTPUT_DIR / f"{ts}_{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)

    midi_json_path = run_dir / "midi.json"
    with midi_json_path.open("w", encoding="utf-8") as f:
        json.dump(midi_data, f, ensure_ascii=False)

    midi_mid_path: Optional[Path] = None
    tempo = int(midi_data.get("meta", {}).get("tempo", meta.get("tempo", 80)))
    if mido is not None:
        try:
            midi_mid_path = _export_pattern_to_mid(midi_data.get("pattern") or [], tempo, run_dir / "midi.mid")
        except Exception:
            midi_mid_path = None

    midi_svg_path: Optional[Path] = None
    try:
        midi_svg_path = _render_pianoroll_svg(midi_data, run_dir / "pianoroll.svg")
    except Exception:
        midi_svg_path = None

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

    # rozbicie midi per instrument (dla warstw melodycznych)
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

            # artefakty na dysku dla konkretnego instrumentu
            safe_inst = str(inst).replace("/", "_").replace("\\", "_")
            inst_json_path = run_dir / f"midi_{safe_inst}.json"
            with inst_json_path.open("w", encoding="utf-8") as f:
                json.dump(inst_midi, f, ensure_ascii=False)

            inst_mid_path: Optional[Path] = None
            try:
                if mido is not None:
                    inst_mid_path = _export_pattern_to_mid(inst_pattern, tempo, run_dir / f"midi_{safe_inst}.mid")
            except Exception:
                inst_mid_path = None

            inst_svg_path: Optional[Path] = None
            try:
                inst_svg_path = _render_pianoroll_svg(inst_midi, run_dir / f"pianoroll_{safe_inst}.svg")
            except Exception:
                inst_svg_path = None

            artifacts_per_instrument[inst] = {
                "midi_json_rel": _rel(inst_json_path),
                "midi_mid_rel": _rel(inst_mid_path) if inst_mid_path else None,
                "midi_image_rel": _rel(inst_svg_path) if inst_svg_path else None,
            }

    # perkusja: budujemy per-instrument na podstawie globalnego pattern (filtr po nutach)
    try:
        midi_meta = midi_data.get("meta") if isinstance(midi_data.get("meta"), dict) else {}
        requested_instruments = (midi_meta.get("instruments") or meta.get("instruments") or [])
        if not isinstance(requested_instruments, list):
            requested_instruments = []

        instrument_configs = (midi_meta.get("instrument_configs") or meta.get("instrument_configs") or [])
        if not isinstance(instrument_configs, list):
            instrument_configs = []

        percussion_names: set[str] = set()
        for cfg in instrument_configs:
            if not isinstance(cfg, dict):
                continue
            role = str(cfg.get("role") or "").strip().lower()
            name = str(cfg.get("name") or "").strip()
            if role == "percussion" and name:
                percussion_names.add(name)

        global_pattern = midi_data.get("pattern") or []
        if not isinstance(global_pattern, list):
            global_pattern = []

        bars_count: Optional[int] = None
        try:
            bars_count = int(midi_meta.get("bars") or meta.get("bars") or 0) or None
        except Exception:
            bars_count = None

        for inst in requested_instruments:
            if not isinstance(inst, str) or not inst.strip():
                continue
            if inst in midi_per_instrument:
                continue

            # tu obsługujemy tylko perkusję (melodyczne instrumenty są rozbijane wcześniej przez layers)
            if percussion_names and inst not in percussion_names:
                continue
            allowed_notes = _notes_for_percussion_instrument(inst)
            if not allowed_notes:
                continue

            inst_pattern = _filter_pattern_by_notes(global_pattern, allowed_notes, bars=bars_count)
            has_any = any((b.get("events") or []) for b in (inst_pattern or []))
            if not has_any:
                # jeśli nie ma żadnych eventów, nie "naprawiamy" tego sztucznymi nutami.
                # w ui i tak lepiej pokazać pusty pattern, ale z poprawnym zakresem taktów.
                if bars_count and bars_count >= 1:
                    inst_pattern = [{"bar": i, "events": []} for i in range(1, bars_count + 1)]
                else:
                    inst_pattern = []

            inst_meta = dict(midi_meta or {})
            inst_meta["instrument"] = inst
            inst_midi = {"meta": inst_meta, "layers": {}, "pattern": inst_pattern}
            midi_per_instrument[inst] = inst_midi

            safe_inst = str(inst).replace("/", "_").replace("\\", "_")
            inst_json_path = run_dir / f"midi_{safe_inst}.json"
            with inst_json_path.open("w", encoding="utf-8") as f:
                json.dump(inst_midi, f, ensure_ascii=False)

            inst_mid_path: Optional[Path] = None
            try:
                if mido is not None:
                    inst_mid_path = _export_pattern_to_mid(inst_pattern, tempo, run_dir / f"midi_{safe_inst}.mid")
            except Exception:
                inst_mid_path = None

            inst_svg_path: Optional[Path] = None
            try:
                inst_svg_path = _render_pianoroll_svg(inst_midi, run_dir / f"pianoroll_{safe_inst}.svg")
            except Exception:
                inst_svg_path = None

            artifacts_per_instrument[inst] = {
                "midi_json_rel": _rel(inst_json_path),
                "midi_mid_rel": _rel(inst_mid_path) if inst_mid_path else None,
                "midi_image_rel": _rel(inst_svg_path) if inst_svg_path else None,
            }
    except Exception:
        # eksport per-instrument jest best-effort; globalne midi ma się udać niezależnie
        pass

    # zapisujemy zbiorczy opis podziału per instrument w jednym pliku,
    # żeby później łatwo testować pipeline'y i diagnostykę
    try:
        per_inst_path = run_dir / "midi_per_instrument.json"
        with per_inst_path.open("w", encoding="utf-8") as f:
            json.dump(midi_per_instrument, f, ensure_ascii=False)
    except Exception:
        pass

    return run_id, midi_data, artifacts, midi_per_instrument, artifacts_per_instrument
