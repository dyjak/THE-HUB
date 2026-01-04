from __future__ import annotations

"""zbieranie artefaktów do eksportu.

ten moduł odpowiada za skanowanie katalogów output poszczególnych kroków pipeline
(`param_generation`, `midi_generation`, `render`) i zwracanie listy plików gotowych
do pobrania.

założenia:
- nie zmieniamy struktury katalogów output (tylko je skanujemy)
- zwracamy także ścieżkę url, jaką backend wystawia do pobrania danego pliku
- dla niektórych kroków folder może mieć prefix z timestampem, więc run_id bywa sufiksem
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from .schemas import ExportFile


@dataclass
class _StepConfig:
    # wewnętrzna konfiguracja kroku (nie jest częścią publicznego api)
    step: str
    output_dir: Path
    url_prefix: str


def _iter_files(root: Path) -> List[Tuple[str, Path, Optional[int]]]:
    """zwraca listę plików z katalogu jako (rel_posix, abs_path, size_bytes)."""
    out: List[Tuple[str, Path, Optional[int]]] = []
    if not root.exists() or not root.is_dir():
        return out
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        try:
            rel = p.relative_to(root).as_posix()
        except Exception:
            rel = p.name
        size = None
        try:
            size = p.stat().st_size
        except Exception:
            size = None
        out.append((rel, p, size))
    out.sort(key=lambda x: x[0])
    return out


def _find_run_dir_by_suffix(output_dir: Path, run_id: str) -> Optional[Path]:
    """szuka katalogu uruchomienia po sufiksie `run_id`.

    część kroków zapisuje output w folderach w stylu `<timestamp>_<run_id>`.
    dlatego dla midi/param szukamy katalogu, którego nazwa kończy się na `run_id`.
    """
    rid = (run_id or "").strip()
    if not rid or not output_dir.exists():
        return None
    matches: List[Path] = []
    try:
        for p in output_dir.iterdir():
            if not p.is_dir():
                continue
            if p.name.endswith(rid):
                matches.append(p)
    except Exception:
        return None
    if not matches:
        return None
    # preferujemy leksykograficznie "najnowszy" folder z timestampem
    matches.sort(key=lambda p: p.name, reverse=True)
    return matches[0]


def collect_render_files(render_output_root: Path, render_run_id: str) -> List[ExportFile]:
    """zbiera pliki renderu dla danego `render_run_id`.

    uwaga: render output jest traktowany jako "źródło prawdy" i jest spodziewany
    dokładnie w folderze `<render_output_root>/<render_run_id>`.
    """
    run_dir = render_output_root / render_run_id
    files: List[ExportFile] = []
    for rel, abs_path, size in _iter_files(run_dir):
        # render jest wystawiony jako /api/audio -> render_output_root
        url = f"/api/audio/{render_run_id}/{rel}"
        files.append(ExportFile(step="render", abs_path=str(abs_path), rel_path=f"{render_run_id}/{rel}", url=url, bytes=size))
    return files


def collect_midi_files(midi_output_root: Path, midi_run_id: str) -> Tuple[List[ExportFile], Optional[str]]:
    """zbiera pliki midi-generation dla runa.

    zwraca:
    - listę plików do eksportu
    - faktyczną nazwę folderu (np. `<timestamp>_<run_id>`), jeśli znaleziono
    """
    run_dir = _find_run_dir_by_suffix(midi_output_root, midi_run_id)
    if run_dir is None:
        return [], None
    folder = run_dir.name
    files: List[ExportFile] = []
    for rel, abs_path, size in _iter_files(run_dir):
        url = f"/api/midi-generation/output/{folder}/{rel}"
        files.append(ExportFile(step="midi_generation", abs_path=str(abs_path), rel_path=f"{folder}/{rel}", url=url, bytes=size))
    return files, folder


def collect_param_files(param_output_root: Path, param_run_id: str) -> Tuple[List[ExportFile], Optional[str]]:
    """zbiera pliki param-generation dla runa.

    analogicznie jak dla midi: folder może zawierać prefix z timestampem.
    """
    run_dir = _find_run_dir_by_suffix(param_output_root, param_run_id)
    if run_dir is None:
        return [], None
    folder = run_dir.name
    files: List[ExportFile] = []
    for rel, abs_path, size in _iter_files(run_dir):
        url = f"/api/param-generation/output/{folder}/{rel}"
        files.append(ExportFile(step="param_generation", abs_path=str(abs_path), rel_path=f"{folder}/{rel}", url=url, bytes=size))
    return files, folder
