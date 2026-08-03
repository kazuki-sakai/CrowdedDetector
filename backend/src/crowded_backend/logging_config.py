from __future__ import annotations

import logging


LOGGER_NAME = "crowded_backend"
_HANDLER_MARKER = "_crowded_backend_handler"


def configure_application_logging() -> None:
    """Emit CrowdedDetector INFO logs without changing third-party log levels."""
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if any(getattr(handler, _HANDLER_MARKER, False) for handler in logger.handlers):
        return

    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(levelname)s: %(name)s: %(message)s")
    )
    setattr(handler, _HANDLER_MARKER, True)
    logger.addHandler(handler)
