from __future__ import annotations
import time
import uuid
from typing import Any, Dict, List, Optional

# bardzo prosty magazyn danych debugowych w pamięci procesu.
#
# zastosowanie:
# - podczas obsługi żądania (np. generowanie planu) tworzymy "run" z unikalnym run_id
# - do runu dopisujemy zdarzenia (etapy, komunikaty, metadane)
# - frontend może później pobrać historię przez endpoint debug
#
# ograniczenia:
# - dane nie są trwałe: znikają po restarcie aplikacji
# - nie ma limitów rozmiaru ani mechanizmu czyszczenia (to narzędzie dev/debug)


class _Run:
    def __init__(self) -> None:
        # identyfikator uruchomienia skrócony do 12 znaków, wygodny do kopiowania
        self.run_id: str = uuid.uuid4().hex[:12]
        # czas startu runu (unix timestamp)
        self.started_at: float = time.time()
        # lista zdarzeń debugowych w kolejności dopisywania
        self.events: List[Dict[str, Any]] = []

    def log(self, stage: str, message: str, data: Optional[Dict[str, Any]] = None) -> None:
        # dopisuje pojedyncze zdarzenie (z timestampem) do listy `events`.
        # `stage` to nazwa etapu (np. "provider_call"), a `message` to krótki opis.
        self.events.append({
            "ts": time.time(),
            "stage": stage,
            "message": message,
            "data": data or None,
        })

    def to_dict(self) -> Dict[str, Any]:
        # konwersja do zwykłego słownika, aby łatwo zwrócić to jako json w fastapi
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "events": self.events,
        }


class _DebugStore:
    def __init__(self) -> None:
        # mapowanie run_id -> obiekt runu
        self._runs: Dict[str, _Run] = {}

    def start(self) -> _Run:
        # tworzy nowy run i zapisuje go w store
        run = _Run()
        self._runs[run.run_id] = run
        return run

    def get(self, run_id: str) -> Optional[Dict[str, Any]]:
        # pobiera dane debugowe dla danego run_id (albo None, jeśli nie ma takiego runu)
        run = self._runs.get(run_id)
        return run.to_dict() if run else None


DEBUG_STORE = _DebugStore()
