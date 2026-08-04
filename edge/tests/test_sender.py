from __future__ import annotations

import sys
from types import ModuleType
import unittest
from unittest.mock import Mock, patch

from crowded_edge.settings import DeviceSettings

requests_stub = ModuleType("requests")
requests_stub.Session = Mock
with patch.dict(sys.modules, {"requests": requests_stub}):
    from crowded_edge.sender import ObservationSender


class ObservationSenderTest(unittest.TestCase):
    def test_sends_device_and_location_assignment(self) -> None:
        settings = DeviceSettings(
            device_id=13,
            location_id=3,
            room_name="大体育館",
            zone_name="左側",
            backend_url="http://example.test/api/v1/observations",
            api_token="test-token",
            timeout_seconds=20,
            verify_tls=False,
            camera_device=0,
            interval_seconds=10,
            width=1280,
            height=720,
            jpeg_quality=85,
        )
        response = Mock()
        response.json.return_value = {
            "accepted": True,
            "device_id": 13,
            "location_id": 3,
            "queue_depth": 1,
        }
        session = Mock()
        session.post.return_value = response

        with patch("crowded_edge.sender.requests.Session", return_value=session):
            sender = ObservationSender(settings)
            result = sender.send(b"jpeg")
            sender.close()

        self.assertTrue(result["accepted"])
        session.post.assert_called_once_with(
            settings.backend_url,
            data={
                "device_id": "13",
                "location_id": "3",
                "room_name": "大体育館",
                "zone_name": "左側",
            },
            files={"image": ("capture.jpg", b"jpeg", "image/jpeg")},
            timeout=20,
            verify=False,
        )
        response.raise_for_status.assert_called_once_with()
        session.close.assert_called_once_with()
