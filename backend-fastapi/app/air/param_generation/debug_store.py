from __future__ import annotations
import time
import uuid
from typing import Any, Dict, List, Optional


class _Run:
    def __init__(self) -> None:
        self.run_id: str = uuid.uuid4().hex[:12]
        self.started_at: float = time.time()
        self.events: List[Dict[str, Any]] = []

    def log(self, stage: str, message: str, data: Optional[Dict[str, Any]] = None) -> None:
        self.events.append({
            "ts": time.time(),
            "stage": stage,
            "message": message,
            "data": data or None,
        })

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "events": self.events,
        }


class _DebugStore:
    def __init__(self) -> None:
        self._runs: Dict[str, _Run] = {}

    def start(self) -> _Run:
        run = _Run()
        self._runs[run.run_id] = run
        return run

    def get(self, run_id: str) -> Optional[Dict[str, Any]]:
        run = self._runs.get(run_id)
        return run.to_dict() if run else None


DEBUG_STORE = _DebugStore()
