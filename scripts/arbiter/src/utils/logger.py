"""Logging configuration."""

import logging
import sys
from datetime import datetime
from pathlib import Path


def setup_logger(name: str, log_dir: str = "logs") -> logging.Logger:
    """
    Setup logger with file and console handlers.

    Args:
        name: Logger name (typically module name)
        log_dir: Directory for log files

    Returns:
        Configured logger instance
    """
    Path(log_dir).mkdir(exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Prevent duplicate handlers
    if logger.handlers:
        return logger

    # File handler - daily log files
    log_file = Path(log_dir) / f"arbiter-{datetime.now().date()}.log"
    fh = logging.FileHandler(log_file, encoding='utf-8')
    fh.setLevel(logging.INFO)

    # Console handler — force UTF-8 on Windows to avoid cp1252 UnicodeEncodeError
    ch = logging.StreamHandler(sys.stdout)
    if hasattr(ch.stream, 'reconfigure'):
        try:
            ch.stream.reconfigure(encoding='utf-8')
        except Exception:
            pass
    ch.setLevel(logging.INFO)

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    logger.addHandler(fh)
    logger.addHandler(ch)

    return logger
