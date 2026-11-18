"""Structured logging with colored console output and rotating file handler.

Provides a factory function to create loggers with consistent formatting,
colored terminal output via colorama, and automatic file logging with rotation.
"""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

import colorama
from colorama import Fore, Style

colorama.init(autoreset=True)

_LOG_DIR: Path = Path("logs")
_LOG_FILE: str = "bot.log"
_MAX_BYTES: int = 5 * 1024 * 1024  # 5 MB
_BACKUP_COUNT: int = 3
_CONSOLE_FORMAT: str = "[%(asctime)s] [%(levelname)-8s] [%(name)s] %(message)s"
_FILE_FORMAT: str = "[%(asctime)s] [%(levelname)-8s] [%(name)s] %(message)s"
_DATE_FORMAT: str = "%H:%M:%S"

_LEVEL_COLORS: dict[int, str] = {
    logging.DEBUG: Fore.CYAN,
    logging.INFO: Fore.GREEN,
    logging.WARNING: Fore.YELLOW,
    logging.ERROR: Fore.RED,
    logging.CRITICAL: Fore.RED + Style.BRIGHT,
}


class _ColoredFormatter(logging.Formatter):
    """Formatter that applies colorama colors based on log level."""

    def __init__(self, fmt: str | None = None, datefmt: str | None = None) -> None:
        super().__init__(fmt=fmt, datefmt=datefmt)

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record with appropriate color for the log level.

        Args:
            record: The log record to format.

        Returns:
            The formatted and colorized log string.
        """
        color: str = _LEVEL_COLORS.get(record.levelno, "")
        formatted: str = super().format(record)
        return f"{color}{formatted}{Style.RESET_ALL}"


def setup_logger(name: str, level: str = "INFO") -> logging.Logger:
    """Create and configure a logger with colored console and rotating file output.

    The logger writes colored output to ``stderr`` and plain-text output to
    ``logs/bot.log`` (with rotation at 5 MB and 3 backups).  The ``logs/``
    directory is created automatically if it does not exist.

    Args:
        name: The name of the logger (typically ``__name__``).
        level: The minimum logging level as an upper-case string
               (e.g. ``"DEBUG"``, ``"INFO"``).

    Returns:
        A fully configured :class:`logging.Logger` instance.
    """
    logger: logging.Logger = logging.getLogger(name)
    numeric_level: int = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(numeric_level)

    # Avoid adding duplicate handlers on repeated calls.
    if logger.handlers:
        return logger

    # --- Console handler (colored) -------------------------------------------
    console_handler: logging.StreamHandler = logging.StreamHandler(sys.stderr)  # type: ignore[type-arg]
    console_handler.setLevel(numeric_level)
    console_formatter: _ColoredFormatter = _ColoredFormatter(
        fmt=_CONSOLE_FORMAT,
        datefmt=_DATE_FORMAT,
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # --- File handler (rotating) ---------------------------------------------
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    file_handler: RotatingFileHandler = RotatingFileHandler(
        filename=str(_LOG_DIR / _LOG_FILE),
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(numeric_level)
    file_formatter: logging.Formatter = logging.Formatter(
        fmt=_FILE_FORMAT,
        datefmt=_DATE_FORMAT,
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    return logger
