from __future__ import annotations

"""schematy danych dla eksportu.

te modele opisują:
- pojedynczy plik możliwy do pobrania (`ExportFile`)
- manifest eksportu (`ExportManifest`) zawierający listę plików i brakujące kroki
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Literal


ExportStep = Literal["param_generation", "midi_generation", "render"]


class ExportFile(BaseModel):
    step: ExportStep
    # ścieżka na dysku (best-effort; może być None dla bezpieczeństwa)
    abs_path: Optional[str] = Field(default=None, exclude=True)
    # ścieżka względna w katalogu output danego kroku
    rel_path: str
    # url do pobrania względny względem backend base, np. /api/audio/<run>/<file>
    url: str
    # best-effort hint rozmiaru
    bytes: Optional[int] = None


class ExportManifest(BaseModel):
    render_run_id: str
    midi_run_id: Optional[str] = None
    param_run_id: Optional[str] = None
    files: List[ExportFile] = Field(default_factory=list)
    missing: List[str] = Field(default_factory=list)
