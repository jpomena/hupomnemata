"""Centralized logging for exceptions handled by the application."""

import logging
from pathlib import Path


LOG_PATH = Path(__file__).resolve().parents[2] / "logs" / "error_log.txt"
LOGGER_NAME = "hupomnemata"


def log_exception(context: str, error: Exception) -> None:
    """Write a handled exception and its traceback to the central log."""
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.ERROR)
    logger.propagate = False

    log_path = LOG_PATH.resolve()
    if not any(
        isinstance(handler, logging.FileHandler)
        and Path(handler.baseFilename).resolve() == log_path
        for handler in logger.handlers
    ):
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(log_path, encoding="utf-8")
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(message)s"
        ))
        logger.addHandler(handler)

    logger.error(
        "%s: %s",
        context,
        error,
        exc_info=(type(error), error, error.__traceback__),
    )
