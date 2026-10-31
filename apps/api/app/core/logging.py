import logging
import sys
import json
from datetime import datetime, timezone
from app.core.config import settings

SENSITIVE_KEYS = {"password", "token", "secret", "jwt", "authorization", "api_key", "access_token", "refresh_token"}

class JSONFormatter(logging.Formatter):
    """Formats logs into structured JSON with sensitive field filtering."""
    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": settings.APP_NAME,
            "environment": settings.APP_ENV,
        }

        # Include request_id if present in record
        if hasattr(record, "request_id"):
            log_obj["request_id"] = record.request_id

        # Redact sensitive parameters if present
        for key in list(log_obj.keys()):
            if any(s in key.lower() for s in SENSITIVE_KEYS):
                log_obj[key] = "[REDACTED]"

        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj)

def setup_logger(name: str = "leadnexus") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(log_level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)

    if settings.APP_ENV == "development" and settings.DEBUG:
        # Human-readable format in local development console
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    else:
        # Production JSON logs
        formatter = JSONFormatter()

    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False
    return logger

def get_logger(name: str = "leadnexus") -> logging.Logger:
    return setup_logger(name)

logger = setup_logger()

