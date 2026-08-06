from __future__ import annotations

import argparse
from html import escape
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import logging
from pathlib import Path
import threading
from typing import Any
from urllib.parse import urlsplit

from crowded_edge.camera import Camera
from crowded_edge.settings import DeviceSettings


LOGGER = logging.getLogger(__name__)
LOOPBACK_ADDRESS = "127.0.0.1"


def render_page(settings: DeviceSettings) -> bytes:
    title = escape(settings.room_name)
    zone = escape(settings.zone_name) if settings.zone_name else "区域指定なし"
    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>カメラ設置プレビュー</title>
  <style>
    :root {{ color-scheme: dark; }}
    body {{
      margin: 0;
      padding: 16px;
      background: #111827;
      color: #f9fafb;
      font-family: system-ui, sans-serif;
    }}
    main {{ max-width: 1280px; margin: 0 auto; }}
    h1 {{ margin: 0 0 4px; font-size: 1.25rem; }}
    p {{ margin: 0 0 12px; color: #d1d5db; }}
    .frame {{
      position: relative;
      overflow: hidden;
      border: 2px solid #f9fafb;
      background: #000;
      line-height: 0;
    }}
    .frame img {{ display: block; width: 100%; height: auto; }}
    .grid {{
      position: absolute;
      inset: 0;
      pointer-events: none;
      background:
        linear-gradient(to right,
          transparent 33.1%, rgba(255,255,255,.55) 33.3%,
          rgba(255,255,255,.55) 33.5%, transparent 33.7%,
          transparent 66.4%, rgba(255,255,255,.55) 66.6%,
          rgba(255,255,255,.55) 66.8%, transparent 67%),
        linear-gradient(to bottom,
          transparent 33.1%, rgba(255,255,255,.55) 33.3%,
          rgba(255,255,255,.55) 33.5%, transparent 33.7%,
          transparent 66.4%, rgba(255,255,255,.55) 66.6%,
          rgba(255,255,255,.55) 66.8%, transparent 67%);
    }}
    #status {{ margin-top: 8px; color: #86efac; }}
    #status.error {{ color: #fca5a5; }}
  </style>
</head>
<body>
  <main>
    <h1>{title}</h1>
    <p>Device {settings.device_id} / Location {settings.location_id} / {zone}
      / 設定解像度 {settings.width}×{settings.height}</p>
    <div class="frame">
      <img id="preview" alt="Webカメラのプレビュー">
      <div class="grid"></div>
    </div>
    <p id="status">映像を取得しています…</p>
  </main>
  <script>
    const image = document.getElementById('preview');
    const status = document.getElementById('status');
    function reload() {{
      image.src = 'frame.jpg?t=' + Date.now();
    }}
    image.onload = () => {{
      status.textContent = 'プレビュー更新中（終了はRaspberry Pi側でCtrl+C）';
      status.className = '';
      window.setTimeout(reload, 200);
    }};
    image.onerror = () => {{
      status.textContent = '映像を取得できません。再試行しています…';
      status.className = 'error';
      window.setTimeout(reload, 1000);
    }};
    reload();
  </script>
</body>
</html>
""".encode("utf-8")


class PreviewServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        address: tuple[str, int],
        settings: DeviceSettings,
        camera: Camera,
    ) -> None:
        super().__init__(address, PreviewRequestHandler)
        self.settings = settings
        self.camera = camera
        self.camera_lock = threading.Lock()


class PreviewRequestHandler(BaseHTTPRequestHandler):
    server: Any

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/":
            self._send(
                HTTPStatus.OK,
                "text/html; charset=utf-8",
                render_page(self.server.settings),
            )
            return
        if path == "/frame.jpg":
            try:
                with self.server.camera_lock:
                    frame = self.server.camera.capture_jpeg()
            except Exception as exc:
                LOGGER.warning("preview frame capture failed: %s", exc)
                self._send(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    "text/plain; charset=utf-8",
                    "camera frame capture failed\n".encode("utf-8"),
                )
                return
            self._send(HTTPStatus.OK, "image/jpeg", frame)
            return
        self._send(
            HTTPStatus.NOT_FOUND,
            "text/plain; charset=utf-8",
            b"not found\n",
        )

    def _send(
        self,
        status: HTTPStatus,
        content_type: str,
        body: bytes,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self' 'unsafe-inline'")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        LOGGER.debug("preview request: " + format, *args)


def run_preview(settings: DeviceSettings, port: int) -> None:
    if not 1 <= port <= 65535:
        raise ValueError("port must be between 1 and 65535")
    with Camera(settings) as camera:
        server = PreviewServer((LOOPBACK_ADDRESS, port), settings, camera)
        try:
            LOGGER.info(
                "camera preview ready at http://%s:%d device_id=%d location_id=%d",
                LOOPBACK_ADDRESS,
                port,
                settings.device_id,
                settings.location_id,
            )
            server.serve_forever(poll_interval=0.2)
        except KeyboardInterrupt:
            LOGGER.info("camera preview stopped")
        finally:
            server.server_close()


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preview the configured camera through an SSH tunnel."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/device.ini"),
        help="path to the device INI file",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="loopback HTTP port (default: 8765)",
    )
    return parser.parse_args()


def main() -> None:
    args = _arguments()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    settings = DeviceSettings.from_file(args.config)
    run_preview(settings, args.port)


if __name__ == "__main__":
    main()
