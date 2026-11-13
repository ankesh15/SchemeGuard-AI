"""One logical Beat leader, protected by a process-lifetime PostgreSQL lock."""

import time
from pathlib import Path
from typing import Any

import psycopg
from celery.beat import Scheduler  # type: ignore[import-untyped]

from app.core.config import get_settings
from app.workers.celery_app import celery_app


class LeaderScheduler(Scheduler):  # type: ignore[misc]
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        settings = get_settings()
        self._leader_connection = psycopg.connect(
            settings.psycopg_dsn,
            autocommit=True,
            connect_timeout=5,
        )
        row = self._leader_connection.execute("SELECT pg_try_advisory_lock(587643123)").fetchone()
        if not row or not row[0]:
            self._leader_connection.close()
            raise RuntimeError("A logical monitoring scheduler is already active")
        super().__init__(*args, **kwargs)

    def tick(self, *args: Any, **kwargs: Any) -> float:
        self._leader_connection.execute("SELECT 1")
        Path("/tmp/schemeguard-beat-heartbeat").write_text(str(time.time()))
        return float(min(10, super().tick(*args, **kwargs)))

    def close(self) -> None:
        self._leader_connection.close()
        super().close()


if __name__ == "__main__":
    celery_app.Beat(scheduler="app.workers.scheduler:LeaderScheduler", max_interval=10, loglevel="INFO").run()
