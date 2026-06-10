"""Gestionnaire de jobs longs (backtests, grid, walk-forward).

Les jobs tournent dans des threads (le grid parallélise lui-même en
processus) ; la progression est poussée sur le canal WebSocket `jobs:{id}`.
"""

from __future__ import annotations

import logging
import threading
import time
import traceback
import uuid
from collections.abc import Callable
from typing import Any

from app.api.ws import hub

log = logging.getLogger(__name__)


class JobManager:
    def __init__(self) -> None:
        self.jobs: dict[str, dict[str, Any]] = {}
        self.lock = threading.Lock()

    def submit(self, kind: str, fn: Callable[[Callable[[int, int], None]], Any]) -> str:
        job_id = uuid.uuid4().hex[:12]
        with self.lock:
            self.jobs[job_id] = {
                "id": job_id,
                "kind": kind,
                "status": "en_cours",
                "progress": 0.0,
                "started_at": int(time.time() * 1000),
                "result": None,
                "error": None,
            }

        def progress(done: int, total: int) -> None:
            pct = 100.0 * done / total if total else 0.0
            with self.lock:
                self.jobs[job_id]["progress"] = pct
            hub.broadcast(f"jobs:{job_id}", {"status": "en_cours", "progress": pct})

        def run() -> None:
            try:
                result = fn(progress)
                with self.lock:
                    self.jobs[job_id].update(status="termine", progress=100.0, result=result)
                hub.broadcast(f"jobs:{job_id}", {"status": "termine", "progress": 100.0})
            except Exception as exc:
                log.error("job %s en erreur : %s\n%s", job_id, exc, traceback.format_exc())
                with self.lock:
                    self.jobs[job_id].update(status="erreur", error=str(exc))
                hub.broadcast(f"jobs:{job_id}", {"status": "erreur", "error": str(exc)})

        threading.Thread(target=run, daemon=True, name=f"job-{kind}-{job_id}").start()
        return job_id

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self.lock:
            job = self.jobs.get(job_id)
            return dict(job) if job else None


job_manager = JobManager()
