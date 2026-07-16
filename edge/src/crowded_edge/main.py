from __future__ import annotations

import argparse
import logging
from pathlib import Path
import signal
import threading
import time

from crowded_edge.camera import Camera
from crowded_edge.sender import ObservationSender
from crowded_edge.settings import DeviceSettings


LOGGER = logging.getLogger(__name__)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture and send crowd images")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/device.ini"),
        help="path to the device INI file",
    )
    parser.add_argument("--once", action="store_true", help="capture once and exit")
    return parser.parse_args()


def run(settings: DeviceSettings, once: bool = False) -> None:
    stopping = threading.Event()

    def stop(_signum: int, _frame: object) -> None:
        stopping.set()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    sender = ObservationSender(settings)
    try:
        with Camera(settings) as camera:
            while not stopping.is_set():
                started = time.monotonic()
                try:
                    image = camera.capture_jpeg()
                    response = sender.send(image)
                    LOGGER.info(
                        "observation accepted device_id=%d queue_depth=%s",
                        settings.device_id,
                        response.get("queue_depth", "unknown"),
                    )
                except Exception:
                    LOGGER.exception("capture or upload failed")
                if once:
                    return
                elapsed = time.monotonic() - started
                stopping.wait(max(0.0, settings.interval_seconds - elapsed))
    finally:
        sender.close()


def main() -> None:
    args = _arguments()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    settings = DeviceSettings.from_file(args.config)
    run(settings, once=args.once)


if __name__ == "__main__":
    main()

