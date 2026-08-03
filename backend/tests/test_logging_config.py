from __future__ import annotations

import logging
import unittest

from crowded_backend.logging_config import (
    LOGGER_NAME,
    configure_application_logging,
)


class LoggingConfigTest(unittest.TestCase):
    def test_enables_info_without_duplicating_handler(self) -> None:
        logger = logging.getLogger(LOGGER_NAME)
        previous_handlers = logger.handlers[:]
        previous_level = logger.level
        previous_propagate = logger.propagate
        try:
            logger.handlers = []
            logger.setLevel(logging.WARNING)
            logger.propagate = True

            configure_application_logging()
            configure_application_logging()

            self.assertTrue(logger.isEnabledFor(logging.INFO))
            self.assertFalse(logger.propagate)
            self.assertEqual(len(logger.handlers), 1)
        finally:
            logger.handlers = previous_handlers
            logger.setLevel(previous_level)
            logger.propagate = previous_propagate


if __name__ == "__main__":
    unittest.main()
