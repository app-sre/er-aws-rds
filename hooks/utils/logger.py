import logging
import logging.config

from .runtime import is_dry_run


class DryRunFilter(logging.Filter):
    """Adds a DRY_RUN prefix"""

    def __init__(self, *, dry_run: bool) -> None:
        super().__init__()
        if dry_run:
            self.prefix = "DRY_RUN - "
        else:
            self.prefix = ""

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter method"""
        record.prefix = self.prefix
        return True


def setup_logging() -> None:
    """Returns a logger"""
    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {"prefix_filter": {"()": DryRunFilter, "dry_run": is_dry_run()}},
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "filters": ["prefix_filter"],
                "formatter": "base",
            }
        },
        "formatters": {"base": {"format": "%(prefix)s%(levelname)s - %(message)s"}},
        "root": {"level": "INFO", "handlers": ["console"]},
        "botocore": {"level": "ERROR", "handlers": ["console"]},
    })
