from __future__ import annotations

from http import HTTPStatus
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from crowded_edge.preview import PreviewRequestHandler, render_page
from crowded_edge.settings import DeviceSettings


def settings() -> DeviceSettings:
    return DeviceSettings(
        device_id=1,
        location_id=1,
        room_name="機械工学科 <展示>",
        zone_name="入口側",
        backend_url="http://example.test/api/v1/observations",
        api_token="secret",
        timeout_seconds=20,
        verify_tls=False,
        camera_device=0,
        interval_seconds=10,
        width=1280,
        height=720,
        jpeg_quality=85,
    )


class FakeCamera:
    def capture_jpeg(self) -> bytes:
        return b"fake-jpeg"


class PreviewTest(unittest.TestCase):
    def test_page_escapes_assignment_and_shows_resolution(self) -> None:
        page = render_page(settings()).decode("utf-8")
        self.assertIn("機械工学科 &lt;展示&gt;", page)
        self.assertNotIn("機械工学科 <展示>", page)
        self.assertIn("設定解像度 1280×720", page)

    def test_serves_jpeg_frame(self) -> None:
        handler = PreviewRequestHandler.__new__(PreviewRequestHandler)
        handler.path = "/frame.jpg?t=123"
        handler.server = SimpleNamespace(
            settings=settings(),
            camera=FakeCamera(),
            camera_lock=threading.Lock(),
        )
        handler._send = Mock()

        handler.do_GET()

        handler._send.assert_called_once_with(
            HTTPStatus.OK,
            "image/jpeg",
            b"fake-jpeg",
        )

    def test_rejects_unknown_path(self) -> None:
        handler = PreviewRequestHandler.__new__(PreviewRequestHandler)
        handler.path = "/missing"
        handler.server = SimpleNamespace(settings=settings())
        handler._send = Mock()

        handler.do_GET()

        handler._send.assert_called_once_with(
            HTTPStatus.NOT_FOUND,
            "text/plain; charset=utf-8",
            b"not found\n",
        )


if __name__ == "__main__":
    unittest.main()
