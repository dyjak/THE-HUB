from __future__ import annotations
from pathlib import Path
import json

# ten plik to pomocniczy "mini pipeline" uruchamiany z konsoli.
#
# zastosowanie:
# - mamy już zapisane outputy z param_generation i midi_generation (pliki json w output/)
# - chcemy szybko odpalić docelowy render audio bez frontendu
# - plik składa dane w `RenderRequest` i woła `render_audio`

from .schemas import RenderRequest, TrackSettings
from .engine import render_audio


def _auto_update_selected_samples(param_run_dir: Path) -> None:
    """lokalny odpowiednik patch /param-generation/plan/{run_id}/selected-samples.

    w tym testowym pipeline bierzemy bardzo prostą heurystykę:
    - dla każdego instrumentu z meta.instruments ustawiamy sample_id = nazwa instrumentu
    - to jest tylko placeholder, żeby zademonstrować przepływ
    - docelowo frontend dostarczy realne id z inventory
    """
    json_path = param_run_dir / "parameter_plan.json"
    if not json_path.exists():
        return
    try:
        doc = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception:
        return
    if not isinstance(doc, dict):
        return
    meta = doc.get("meta")
    if not isinstance(meta, dict):
        meta = {}
        doc["meta"] = meta
    instruments = meta.get("instruments") or []
    if not isinstance(instruments, list):
        instruments = []
    selected: dict[str, str] = {}
    for inst in instruments:
        if not isinstance(inst, str):
            continue
        name = inst.strip()
        if not name:
            continue
        # placeholder: używamy nazwy instrumentu jako id;
        # inventory i frontend mogą nadpisać to realnymi id sampli
        selected[name] = name
    if not selected:
        return
    meta["selected_samples"] = selected
    try:
        json_path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    except Exception:
        return


def run_mini_render(
    param_run_dir: Path,
    midi_run_dir: Path,
    run_id: str | None = None,
):
    """mini-pipeline: wczytuje istniejące outputy z param_generation i midi_generation i uruchamia render.

    założenia (obecny stan projektu):
    - param_generation zapisuje json z meta pod nazwą parameter_plan.json
    - midi_generation zapisuje midi.json w katalogu run
    - wybór sampli z inventory jest rozstrzygnięty wcześniej (param_generation),
      więc tutaj tylko odtwarzamy gotowy plan midi
    """

    param_json = param_run_dir / "parameter_plan.json"
    midi_json = midi_run_dir / "midi.json"
    # opcjonalnie: per-instrument podział midi z modułu midi_generation
    midi_per_instrument: dict[str, dict] | None = None

    if not param_json.exists():
        raise FileNotFoundError(f"Missing parameter_plan.json in {param_run_dir}")
    if not midi_json.exists():
        raise FileNotFoundError(f"Missing midi.json in {midi_run_dir}")

    # najpierw upewniamy się, że meta.selected_samples jest obecne choćby jako placeholder,
    # tak jak zrobiłby to patch w param_generation
    _auto_update_selected_samples(param_run_dir)

    meta = json.loads(param_json.read_text(encoding="utf-8")).get("meta", {})
    midi = json.loads(midi_json.read_text(encoding="utf-8"))

    # próbujemy wczytać dodatkowy plik z podziałem per instrument, jeśli istnieje
    try:
        per_inst_path = midi_run_dir / "midi_per_instrument.json"
        if per_inst_path.exists():
            midi_per_instrument = json.loads(per_inst_path.read_text(encoding="utf-8"))
    except Exception:
        midi_per_instrument = None

    # bazujemy na instrumentach z meta.instruments; frontend docelowo może przekazywać
    # dokładniejsze TrackSettings, ale tu robimy prostą mapę
    instruments = meta.get("instruments") or midi.get("meta", {}).get("instruments") or []
    selected_samples: dict[str, str] = {}
    raw_selected = meta.get("selected_samples") or {}
    if isinstance(raw_selected, dict):
        for k, v in raw_selected.items():
            if not isinstance(k, str) or not isinstance(v, str):
                continue
            name = k.strip()
            sid = v.strip()
            if not name or not sid:
                continue
            selected_samples[name] = sid
    tracks: list[TrackSettings] = []
    for name in instruments:
        # domyślnie każdy instrument włączony, głośność 0 db, pan 0
        tracks.append(TrackSettings(instrument=str(name)))

    if not tracks:
        raise ValueError("No instruments found in meta to build tracks list")

    # run_id może pochodzić z zewnątrz (np. ui),
    # tu fallbackujemy do nazwy katalogu midi_generation
    if run_id is None:
        run_id = midi_run_dir.name

    req = RenderRequest(
        project_name=str(meta.get("style") or "air_demo"),
        run_id=run_id,
        midi=midi,
        midi_per_instrument=midi_per_instrument,
        tracks=tracks,
        selected_samples=selected_samples or None,
    )

    return render_audio(req)


def _pick_latest_run(output_root: Path) -> Path:
    """zwraca katalog o "najnowszej" nazwie (sort leksykalny) z danego output_root."""
    if not output_root.is_dir():
        raise FileNotFoundError(f"Output root not found: {output_root}")
    dirs = [p for p in output_root.iterdir() if p.is_dir()]
    if not dirs:
        raise FileNotFoundError(f"No run directories found in {output_root}")
    # nazwy mają prefiks z datą/czasem, więc sortowanie leksykalne działa jako proxy czasu
    dirs.sort(key=lambda p: p.name)
    return dirs[-1]


if __name__ == "__main__":
    # interaktywne uruchomienie: pozwalamy wpisać nazwy folderów albo zostawić puste,
    # wtedy automatycznie wybieramy najnowsze runy z obu modułów
    base = Path(__file__).resolve().parent

    print("Mini render pipeline")
    print("Jeśli zostawisz pole puste, zostanie wybrany NAJNOWSZY run z output/.\n")

    param_root = base.parent / "param_generation" / "output"
    midi_root = base.parent / "midi_generation" / "output"

    print(f"param_generation output root: {param_root}")
    print(f"midi_generation output root:  {midi_root}\n")

    param_folder = input("Podaj NAZWĘ folderu z param_generation/output (ENTER = najnowszy): ").strip()
    midi_folder = input("Podaj NAZWĘ folderu z midi_generation/output (ENTER = najnowszy): ").strip()

    if param_folder:
        param_dir = param_root / param_folder
        if not param_dir.is_dir():
            raise FileNotFoundError(f"Nie znaleziono katalogu param_generation: {param_dir}")
    else:
        param_dir = _pick_latest_run(param_root)
        print(f"[auto] wybrano najnowszy param run: {param_dir.name}")

    if midi_folder:
        midi_dir = midi_root / midi_folder
        if not midi_dir.is_dir():
            raise FileNotFoundError(f"Nie znaleziono katalogu midi_generation: {midi_dir}")
    else:
        midi_dir = _pick_latest_run(midi_root)
        print(f"[auto] wybrano najnowszy midi run:  {midi_dir.name}")

    # run_id do rendera ustawiamy na pełną nazwę katalogu MIDI (żeby było jednoznaczne).
    result = run_mini_render(param_dir, midi_dir, run_id=midi_dir.name)
    print("Render result:", result)