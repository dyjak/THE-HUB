from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pathlib import Path
from typing import Optional

from starlette.background import BackgroundTask
from starlette.responses import StreamingResponse

import tempfile
import zipfile
from pathlib import PurePosixPath

from .schemas import ExportManifest
from .collector import collect_render_files, collect_midi_files, collect_param_files
from .links import get_param_for_render


router = APIRouter(
    prefix="/air/export",
    tags=["air:export"],
)


def _paths() -> tuple[Path, Path, Path]:
    # Local output roots (kept consistent with the step modules)
    here = Path(__file__).resolve()
    air_root = here.parents[1]
    param_root = air_root / "param_generation" / "output"
    midi_root = air_root / "midi_generation" / "output"
    render_root = air_root / "render" / "output"
    return param_root, midi_root, render_root


def _build_manifest(render_run_id: str, param_run_id: Optional[str] = None) -> ExportManifest:
    rid = (render_run_id or "").strip()
    if not rid:
        raise HTTPException(status_code=422, detail={"error": "invalid_run_id"})

    param_root, midi_root, render_root = _paths()

    manifest = ExportManifest(render_run_id=rid)

    # Render files (authoritative)
    render_files = collect_render_files(render_root, rid)
    if not render_files:
        manifest.missing.append("render")
    manifest.files.extend(render_files)

    # MIDI files (usually the same run_id)
    midi_files, _midi_folder = collect_midi_files(midi_root, rid)
    if midi_files:
        manifest.midi_run_id = rid
        manifest.files.extend(midi_files)
    else:
        manifest.missing.append("midi_generation")

    # Param files (need param_run_id; best-effort resolve from stored link)
    pid = (param_run_id or "").strip() or (get_param_for_render(rid) or "")
    if pid:
        param_files, _param_folder = collect_param_files(param_root, pid)
        if param_files:
            manifest.param_run_id = pid
            manifest.files.extend(param_files)
        else:
            manifest.missing.append("param_generation")
    else:
        manifest.missing.append("param_generation")

    manifest.files.sort(key=lambda f: (f.step, f.rel_path))
    return manifest


def _safe_arcname(step: str, rel_path: str) -> str:
    rel_posix = (rel_path or "").replace("\\", "/")
    rel_posix = rel_posix.lstrip("/")
    p = PurePosixPath(rel_posix)
    parts = [part for part in p.parts if part not in (".", "..", "")]
    safe_rel = "/".join(parts) if parts else "file"
    return f"{step}/{safe_rel}"


@router.get("/list/{render_run_id}", response_model=ExportManifest)
def export_list(render_run_id: str, param_run_id: Optional[str] = None) -> ExportManifest:
    """Return a manifest of all exportable files for a project.

    The stable project identifier used by the app is the render run_id.
    We always include render outputs, try to include midi outputs for the same
    run_id, and include param outputs if we can resolve the param_run_id.

    We do NOT change any existing output file structures. We only scan folders.
    """

    return _build_manifest(render_run_id=render_run_id, param_run_id=param_run_id)


@router.get("/zip/{render_run_id}")
def export_zip(render_run_id: str, param_run_id: Optional[str] = None) -> StreamingResponse:
    """Download a ZIP containing all exportable artifacts for a project."""

    manifest = _build_manifest(render_run_id=render_run_id, param_run_id=param_run_id)

    # Build ZIP (best-effort; skips missing/unreadable files)
    tmp = tempfile.SpooledTemporaryFile(max_size=64 * 1024 * 1024)
    used: dict[str, int] = {}
    with zipfile.ZipFile(tmp, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for f in manifest.files:
            abs_path = getattr(f, "abs_path", None)
            if not abs_path:
                continue
            try:
                p = Path(abs_path)
                if not p.exists() or not p.is_file():
                    continue
            except Exception:
                continue

            arc = _safe_arcname(str(f.step), str(f.rel_path))
            # Avoid duplicate arcnames
            n = used.get(arc, 0)
            if n:
                stem = arc
                suffix = ""
                if "." in arc.rsplit("/", 1)[-1]:
                    base, ext = arc.rsplit(".", 1)
                    stem = base
                    suffix = "." + ext
                arc = f"{stem}__{n}{suffix}"
            used[arc] = used.get(arc, 0) + 1

            try:
                zf.write(p, arcname=arc)
            except Exception:
                continue

    tmp.seek(0)

    filename = f"export_{manifest.render_run_id}.zip"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
    }
    return StreamingResponse(
        tmp,
        media_type="application/zip",
        headers=headers,
        background=BackgroundTask(tmp.close),
    )
