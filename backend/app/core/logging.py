import json
import logging
import logging.config
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage()
            if record.name.startswith(("schemeguard", "alembic", "uvicorn"))
            else "dependency_log",
        }
        for key in (
            "request_id",
            "method",
            "route",
            "status_code",
            "duration_ms",
            "error_type",
            "job_id",
            "attempt",
        ):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        # Exception text, SQL, URLs, request bodies, and headers can contain secrets.
        if record.exc_info and record.exc_info[0]:
            payload["error_type"] = record.exc_info[0].__name__
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str) -> None:
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {"json": {"()": JsonFormatter}},
            "handlers": {
                "stdout": {
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                    "formatter": "json",
                }
            },
            "root": {"handlers": ["stdout"], "level": level},
            "loggers": {
                "uvicorn": {"handlers": ["stdout"], "level": level, "propagate": False},
                "uvicorn.error": {"handlers": ["stdout"], "level": level, "propagate": False},
                "uvicorn.access": {"handlers": [], "propagate": False},
                "sqlalchemy.engine": {"handlers": [], "level": "WARNING", "propagate": False},
            },
        }
    )
