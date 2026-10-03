"""Logging: one console stream for the whole invocation, plus one run.log inside each results folder."""

import logging
from pathlib import Path

LOGGER = "veredact"
_FMT = logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%Y-%m-%d %H:%M:%S")


def get_logger() -> logging.Logger:
    log = logging.getLogger(LOGGER)
    if not log.handlers:
        h = logging.StreamHandler()
        h.setFormatter(_FMT)
        log.addHandler(h)
        log.setLevel(logging.INFO)
        log.propagate = False
    return log


def add_file(path: Path) -> logging.Handler:
    h = logging.FileHandler(path, mode="w")
    h.setFormatter(_FMT)
    get_logger().addHandler(h)
    return h


def remove(handler: logging.Handler) -> None:
    get_logger().removeHandler(handler)
    handler.close()
