"""Structured logging setup.

Every log record carries a ``request_id`` (set by RequestContextMiddleware via
a contextvar) so all lines from one HTTP request can be correlated. Output is
human-readable text in development and JSON when JEAI_LOG_JSON=true.
"""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        # Carry any structured extras (logger.info(..., extra={...}))
        for key, value in record.__dict__.items():
            if key in payload or key in _STDLIB_RECORD_ATTRS:
                continue
            payload[key] = value
        return json.dumps(payload, default=str)


_STDLIB_RECORD_ATTRS = frozenset(
    logging.LogRecord("", 0, "", 0, "", (), None).__dict__
) | {"request_id", "taskName"}

TEXT_FORMAT = "%(asctime)s %(levelname)-8s [%(request_id)s] %(name)s: %(message)s"


def setup_logging(level: str = "INFO", json_logs: bool = False) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestIdFilter())
    handler.setFormatter(
        JsonFormatter() if json_logs else logging.Formatter(TEXT_FORMAT)
    )
    log_level = level.upper()

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(log_level)
    root.disabled = False

    # Put the app namespace on its own handler so Uvicorn's logging config
    # cannot accidentally swallow application logs under --reload.
    app_logger = logging.getLogger("app")
    app_logger.handlers.clear()
    app_logger.addHandler(handler)
    app_logger.setLevel(log_level)
    app_logger.propagate = False
    app_logger.disabled = False

    # Route Uvicorn through the root handler for consistent formatting. Disable
    # its access log in favour of RequestContextMiddleware's app.request line.
    for name in ("uvicorn", "uvicorn.error"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.setLevel(log_level)
        logger.propagate = True
        logger.disabled = False
    access = logging.getLogger("uvicorn.access")
    access.handlers.clear()
    access.propagate = False
    access.disabled = True
