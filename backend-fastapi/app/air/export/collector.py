from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from .schemas import ExportFile


@dataclass
class _StepConfig:
    step: str
    output_dir: Path
    url_prefix: str


def _iter_files(root: Path) -> List[Tuple[str, Path, Optional[int]]]:
    """Return (rel_posix, abs_path, size_bytes)."""
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
    # Prefer lexicographically newest timestamped folder
    matches.sort(key=lambda p: p.name, reverse=True)
    return matches[0]


def collect_render_files(render_output_root: Path, render_run_id: str) -> List[ExportFile]:
    run_dir = render_output_root / render_run_id
    files: List[ExportFile] = []
    for rel, abs_path, size in _iter_files(run_dir):
        # render is mounted at /api/audio -> render_output_root
        url = f"/api/audio/{render_run_id}/{rel}"
        files.append(ExportFile(step="render", abs_path=str(abs_path), rel_path=f"{render_run_id}/{rel}", url=url, bytes=size))
    return files


def collect_midi_files(midi_output_root: Path, midi_run_id: str) -> Tuple[List[ExportFile], Optional[str]]:
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
    run_dir = _find_run_dir_by_suffix(param_output_root, param_run_id)
    if run_dir is None:
        return [], None
    folder = run_dir.name
    files: List[ExportFile] = []
    for rel, abs_path, size in _iter_files(run_dir):
        url = f"/api/param-generation/output/{folder}/{rel}"
        files.append(ExportFile(step="param_generation", abs_path=str(abs_path), rel_path=f"{folder}/{rel}", url=url, bytes=size))
    return files, folder
