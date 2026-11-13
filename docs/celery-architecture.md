# Background processing

The existing backend image serves api, worker and scheduler. Redis 7.4 is a broker with AOF persistence and no public port; PostgreSQL is the authoritative durable job/status store. Broker messages contain only job UUIDs, never documents, citizen profiles or secrets. Results are stored in PostgreSQL, not a second Celery result backend.

Celery 5.7 uses JSON-only serialization, late acknowledgement, rejection on worker loss, prefetch 1, concurrency 2, and child recycling after 50 jobs. Two queues separate document work from monitoring/comparison. Soft/hard task limits are 420/480 seconds; the PostgreSQL lease is 600 seconds and Redis visibility timeout 900. A nine-minute stop grace period allows warm shutdown. Tasks are idempotent under duplicate or late delivery.

Beat schedules only the dispatcher every 30 seconds. A process-lifetime PostgreSQL advisory lock permits one logical Beat leader even if an operator accidentally starts another scheduler. Connection loss stops the leader; health checks require a recent heartbeat. Per-source daily/weekly UTC schedules live in PostgreSQL and can change without rebuilding Beat's schedule file.

The dispatcher locks due monitor configurations, creates deduplicated jobs and monitoring runs, then sends eligible PostgreSQL outbox IDs to Redis. Publication and enqueue are separate transactions, so a crash can resend a message; the consumer's advisory lock, row claim, lease and terminal-state check make that safe. A broker outage leaves durable jobs available for later dispatch. Failed or crashed tasks are re-dispatched after their next retry time/expired lease. Attempts are bounded. Transient fetch/timeouts retry with exponential backoff and the source's minimum interval. Unsafe URLs and malformed PDFs fail without repeated external access.

Task kinds: MONITOR fetches and versions official PDFs; DOCUMENT invokes the existing parser/LangGraph; COMPARE produces immutable comparison snapshots. PROBE exercises delivery without external requests. The dispatcher redelivers expired RUNNING jobs; an executing task's advisory lock prevents simultaneous processing even after a stale lease. PostgreSQL ownership, not Celery's task-ID metadata, controls business idempotence.

```bash
docker compose up --build -d
docker compose logs -f worker scheduler
docker compose restart worker scheduler
python3 scripts/verify_workers.py
```

Workers do not hot-reload Python modules. Restart them after backend changes. API/frontend hot reload remains enabled. API alone applies migrations before dependent workers start; workers never race startup migrations or seed commands. Live monitoring is opt-in and is initially empty. Do not enroll all static catalog records automatically.

References: [Celery tasks](https://docs.celeryq.dev/en/stable/userguide/tasks.html), [Redis transport](https://docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/redis.html), [single periodic scheduler](https://docs.celeryq.dev/en/stable/userguide/periodic-tasks.html).
