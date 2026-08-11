# Centralized logging setup shared by all backend app modules.
# Routes INFO/DEBUG records to stdout and WARNING/ERROR/CRITICAL records to stderr,
# so `docker logs`/journald consumers can separate normal activity from problems.

import logging
import sys


class _MaxLevelFilter(logging.Filter):
    """Only allow records strictly below `max_level` through (keeps INFO/DEBUG off stderr)."""

    def __init__(self, max_level: int):
        super().__init__()
        self.max_level = max_level

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno < self.max_level


def get_logger(name: str = "mira") -> logging.Logger:
    """Return a logger configured to split output between stdout and stderr by level."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # already configured — avoid duplicate handlers on reimport

    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    log_format = logging.Formatter("%(levelname)s:     %(asctime)s: %(message)s")

    # DEBUG/INFO -> stdout
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.DEBUG)
    stdout_handler.addFilter(_MaxLevelFilter(logging.WARNING))
    stdout_handler.setFormatter(log_format)

    # WARNING/ERROR/CRITICAL -> stderr
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.WARNING)
    stderr_handler.setFormatter(log_format)

    logger.addHandler(stdout_handler)
    logger.addHandler(stderr_handler)
    return logger


# Shared logger instance — import this from other app modules instead of calling get_logger() again.
logger = get_logger()
