from __future__ import annotations

"""prosty magazyn projektów dla air.

ten moduł przechowuje projekty jako pliki json w katalogu `output/` obok kodu.
to podejście jest celowo minimalne:
- brak bazy danych (łatwo przenośne, dobre do prototypu i lokalnych uruchomień)
- operacje są idempotentne i best-effort (błędy odczytu zwracają `None`)
- zapis wykonuje merge (nadpisuje tylko klucze podane w `data`)
"""
from pathlib import Path
from typing import Any, Dict, Optional
import json

ROOT = Path(__file__).parent / "output"
ROOT.mkdir(parents=True, exist_ok=True)


def _project_path(project_id: str) -> Path:
    """mapuje `project_id` na ścieżkę pliku json w katalogu `output/`."""
    return ROOT / f"{project_id}.json"


def load_project(project_id: str) -> Optional[Dict[str, Any]]:
    """wczytuje projekt z dysku.

    zwraca:
    - słownik z danymi projektu, jeśli plik istnieje i da się go sparsować
    - `None`, jeśli pliku nie ma albo jest niepoprawny
    """
    path = _project_path(project_id)
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_project(project_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """zapisuje projekt na dysk, wykonując merge z wcześniejszą wersją.

    zasada merge:
    - jeśli plik istnieje, wczytujemy go (best-effort)
    - wynik to `{**existing, **data}` (czyli klucze z `data` nadpisują poprzednie)
    - zawsze ustawiamy `project_id` w wyniku
    """
    path = _project_path(project_id)
    existing: Dict[str, Any] = {}
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as f:
                existing = json.load(f) or {}
        except Exception:
            existing = {}
    merged = {**existing, **data}
    merged["project_id"] = project_id
    with path.open("w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    return merged
