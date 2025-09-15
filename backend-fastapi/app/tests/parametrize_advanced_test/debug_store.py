from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import List, Dict, Any
import time
import uuid


@dataclass
class DebugEvent:
    ts: float
    stage: str
    message: str
    data: Dict[str, Any] | None = None

    def to_dict(self):
        return asdict(self)


class DebugRun:
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.events: List[DebugEvent] = []

    def log(self, stage: str, message: str, data: Dict[str, Any] | None = None):
        self.events.append(DebugEvent(time.time(), stage, message, data))

    def serialize(self):
        return {
            "run_id": self.run_id,
            "events": [e.to_dict() for e in self.events]
        }


class DebugStore:
    def __init__(self):
        self._runs: Dict[str, DebugRun] = {}

    def start(self) -> DebugRun:
        rid = uuid.uuid4().hex[:12]
        run = DebugRun(rid)
        self._runs[rid] = run
        run.log("run", "started")
        return run

    def get(self, run_id: str) -> Dict[str, Any] | None:
        run = self._runs.get(run_id)
        return run.serialize() if run else None


DEBUG_STORE = DebugStore()
