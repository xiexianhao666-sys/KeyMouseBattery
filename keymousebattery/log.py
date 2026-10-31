"""日志：写到 data\\keymousebattery.log，控制台模式同时打 stderr。"""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

LOGGER_NAME = "keymousebattery"


def setup(folder: Path, verbose: bool = False) -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.DEBUG)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    file_handler = logging.handlers.RotatingFileHandler(
        folder / "keymousebattery.log", maxBytes=512 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
    logger.addHandler(file_handler)
    if verbose and sys.stderr is not None:
        stream = logging.StreamHandler(sys.stderr)
        stream.setFormatter(logging.Formatter("%(levelname)-7s %(name)s: %(message)s"))
        logger.addHandler(stream)
    logger.propagate = False
    return logger


def get(name: str = "") -> logging.Logger:
    return logging.getLogger(LOGGER_NAME + ("." + name if name else ""))
