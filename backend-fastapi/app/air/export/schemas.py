from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional, List, Literal


ExportStep = Literal["param_generation", "midi_generation", "render"]


class ExportFile(BaseModel):
    step: ExportStep
    # Path on disk (best-effort; may be None for safety)
    abs_path: Optional[str] = Field(default=None, exclude=True)
    # Relative path within the step output directory
    rel_path: str
    # Download URL path relative to backend base, e.g. /api/audio/<run>/<file>
    url: str
    # Best-effort size hint
    bytes: Optional[int] = None


class ExportManifest(BaseModel):
    render_run_id: str
    midi_run_id: Optional[str] = None
    param_run_id: Optional[str] = None
    files: List[ExportFile] = Field(default_factory=list)
    missing: List[str] = Field(default_factory=list)
