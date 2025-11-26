from __future__ import annotations
from pathlib import Path
import json

from .schemas import RenderRequest, TrackSettings
from .engine import render_audio


def _auto_update_selected_samples(param_run_dir: Path) -> None:
    """Lokalny odpowiednik PATCH /param-generation/plan/{run_id}/selected-samples.

    W testowym pipeline bierzemy prostą heurystykę: dla każdego instrumentu
    z meta.instruments ustawiamy sample_id = nazwa_instrumentu (to pozwala
    zademonstrować przepływ; docelowo front dostarczy realne ID z inventory).
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
        # placeholder: używamy nazwy instrumentu jako ID; inventory
        # i frontend mogą nadpisać to realnymi ID sampli.
        selected[name] = name
    if not selected:
        return
    meta["selected_samples"] = selected
    try:
        json_path.write_text(json.dumps(doc), encoding="utf-8")
    except Exception:
        return


def run_mini_render(
    param_run_dir: Path,
    midi_run_dir: Path,
    run_id: str | None = None,
):
    """Mini-pipeline: wczytuje istniejące outputy z param_generation + midi_generation
    i uruchamia docelowy render.

    Założenia (obecny stan projektu):
    - param_generation zapisuje JSON z meta pod nazwą parameter_plan.json,
    - midi_generation zapisuje midi.json w swoim katalogu run,
    - wybór sampli z inventory jest już rozstrzygnięty wcześniej (param_generation),
      więc tutaj tylko odtwarzamy gotowy plan MIDI.
    """

    param_json = param_run_dir / "parameter_plan.json"
    midi_json = midi_run_dir / "midi.json"
    # opcjonalnie: per-instrument podział MIDI z modułu midi_generation
    midi_per_instrument: dict[str, dict] | None = None

    if not param_json.exists():
        raise FileNotFoundError(f"Missing parameter_plan.json in {param_run_dir}")
    if not midi_json.exists():
        raise FileNotFoundError(f"Missing midi.json in {midi_run_dir}")

    # Najpierw upewniamy się, że meta.selected_samples jest obecne choćby jako
    # placeholder, tak jak zrobiłby to PATCH w param_generation.
    _auto_update_selected_samples(param_run_dir)

    meta = json.loads(param_json.read_text(encoding="utf-8")).get("meta", {})
    midi = json.loads(midi_json.read_text(encoding="utf-8"))

    # spróbuj wczytać dodatkowy plik z podziałem per instrument, jeśli istnieje
    try:
        per_inst_path = midi_run_dir / "midi_per_instrument.json"
        if per_inst_path.exists():
            midi_per_instrument = json.loads(per_inst_path.read_text(encoding="utf-8"))
    except Exception:
        midi_per_instrument = None

    # Bazujemy na instrumentach z meta.instruments; frontend docelowo może
    # przekazywać dokładniejsze TrackSettings, ale tu robimy prostą mapę.
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
        # domyślnie każdy instrument włączony, głośność 0 dB, pan 0
        tracks.append(TrackSettings(instrument=str(name)))

    if not tracks:
        raise ValueError("No instruments found in meta to build tracks list")

    # run_id może pochodzić z zewnątrz (np. UI),
    # tu fallbackujemy do nazwy katalogu midi_generation.
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


if __name__ == "__main__":
    # Interaktywne uruchomienie: pytamy o nazwy folderów (run_id) dla
    # param_generation i midi_generation bez datowego prefiksu.
    base = Path(__file__).resolve().parent

    print("Mini render pipeline")
    param_folder = input("Podaj NAZWĘ folderu z param_generation/output (np. 20251126_143015_58273ec4c712): ").strip()
    midi_folder = input("Podaj NAZWĘ folderu z midi_generation/output (np. 20251126_143154_110e9346e0e0): ").strip()

    if not param_folder or not midi_folder:
        raise SystemExit("Nazwy folderów nie mogą być puste")

    # Korzystamy bezpośrednio z pełnych nazw folderów podanych przez użytkownika.
    param_root = base.parent / "param_generation" / "output"
    midi_root = base.parent / "midi_generation" / "output"

    param_dir = param_root / param_folder
    midi_dir = midi_root / midi_folder

    if not param_dir.is_dir():
        raise FileNotFoundError(f"Nie znaleziono katalogu param_generation: {param_dir}")
    if not midi_dir.is_dir():
        raise FileNotFoundError(f"Nie znaleziono katalogu midi_generation: {midi_dir}")

    # run_id do rendera ustawiamy na pełną nazwę katalogu MIDI (żeby było jednoznaczne).
    result = run_mini_render(param_dir, midi_dir, run_id=midi_dir.name)
    print("Render result:", result)





"""
Plik WAV ma dodatkowe „chunk-i” (np. metadane, LIST/INFO, ADTL, itp.), których wavfile.read nie rozpoznaje jako audio.
Biblioteka wtedy wypisuje:
WavFileWarning: Chunk (non-data) not understood, skipping it.
i po prostu ignoruje te fragmenty, czytając dalej główny chunk z danymi audio (data).
"""