"""Application logging configuration."""

from __future__ import annotations

import logging
import os
import sys


def configure_logging(app) -> None:
    level_name = os.getenv("LOG_LEVEL", "INFO" if not app.debug else "DEBUG").upper()
    level = getattr(logging, level_name, logging.INFO)

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s [%(name)s] %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )

    app.logger.handlers.clear()
    app.logger.addHandler(handler)
    app.logger.setLevel(level)
    app.logger.propagate = False

    werkzeug_logger = logging.getLogger("werkzeug")
    werkzeug_logger.setLevel(logging.WARNING if not app.debug else logging.INFO)
