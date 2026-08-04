from __future__ import annotations

import os
import tempfile
import time
import unittest
from unittest.mock import patch

try:
    from fastapi.testclient import TestClient
except ImportError:
    TestClient = None


@unittest.skipIf(TestClient is None, "FastAPI test dependencies are not installed")
class ApiTest(unittest.TestCase):
    def test_random_detector_result_reaches_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            environment = {
                "CROWDED_DATA_DIR": directory,
                "CROWDED_API_KEY": "test-key-1234567",
                "CROWDED_DETECTOR": "random",
                "CROWDED_RANDOM_MIN_COUNT": "17",
                "CROWDED_RANDOM_MAX_COUNT": "17",
            }
            with patch.dict(os.environ, environment, clear=True):
                from crowded_backend.main import app

                with TestClient(app) as client:
                    accepted = client.post(
                        "/api/v1/observations",
                        headers={"X-API-Key": "test-key-1234567"},
                        data={"device_id": "2", "room_name": "ランダム検出テスト"},
                        files={"image": ("capture.jpg", b"\xff\xd8\xfftest", "image/jpeg")},
                    )
                    self.assertEqual(accepted.status_code, 202)
                    self.assertEqual(accepted.json()["location_id"], 2)

                    rooms = []
                    deadline = time.monotonic() + 2
                    while time.monotonic() < deadline:
                        response = client.get(
                            "/api/v1/rooms/snapshot",
                            headers={"X-API-Key": "test-key-1234567"},
                        )
                        rooms = response.json()["rooms"]
                        if rooms:
                            break
                        time.sleep(0.01)
                    self.assertEqual(rooms[0]["person_count"], 17)

    def test_multiple_devices_are_aggregated_by_location(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            environment = {
                "CROWDED_DATA_DIR": directory,
                "CROWDED_API_KEY": "test-key-1234567",
                "CROWDED_DETECTOR": "random",
                "CROWDED_RANDOM_MIN_COUNT": "4",
                "CROWDED_RANDOM_MAX_COUNT": "4",
                "CROWDED_MAX_DEVICES": "24",
                "CROWDED_MAX_LOCATIONS": "12",
                "CROWDED_DEVICE_STALE_SECONDS": "35",
            }
            with patch.dict(os.environ, environment, clear=True):
                from crowded_backend.main import app

                with TestClient(app) as client:
                    for device_id, zone_name in ((13, "左側"), (14, "右側")):
                        accepted = client.post(
                            "/api/v1/observations",
                            headers={"X-API-Key": "test-key-1234567"},
                            data={
                                "device_id": str(device_id),
                                "location_id": "3",
                                "room_name": "大体育館",
                                "zone_name": zone_name,
                            },
                            files={
                                "image": (
                                    "capture.jpg",
                                    b"\xff\xd8\xfftest",
                                    "image/jpeg",
                                )
                            },
                        )
                        self.assertEqual(accepted.status_code, 202)

                    room = None
                    deadline = time.monotonic() + 2
                    while time.monotonic() < deadline:
                        response = client.get(
                            "/api/v1/rooms/snapshot",
                            headers={"X-API-Key": "test-key-1234567"},
                        )
                        rooms = response.json()["rooms"]
                        if rooms and rooms[0]["active_device_count"] == 2:
                            room = rooms[0]
                            break
                        time.sleep(0.01)

                    self.assertIsNotNone(room)
                    self.assertEqual(room["id"], 3)
                    self.assertEqual(room["person_count"], 8)
                    self.assertEqual(room["camera_status"], "ok")
                    self.assertEqual(room["device_count"], 2)
                    self.assertEqual(
                        [device["zone_name"] for device in room["devices"]],
                        ["左側", "右側"],
                    )

    def test_rejects_location_out_of_range(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            environment = {
                "CROWDED_DATA_DIR": directory,
                "CROWDED_API_KEY": "test-key-1234567",
                "CROWDED_DETECTOR": "mock",
                "CROWDED_MAX_DEVICES": "24",
                "CROWDED_MAX_LOCATIONS": "12",
            }
            with patch.dict(os.environ, environment, clear=True):
                from crowded_backend.main import app

                with TestClient(app) as client:
                    response = client.post(
                        "/api/v1/observations",
                        headers={"X-API-Key": "test-key-1234567"},
                        data={
                            "device_id": "13",
                            "location_id": "13",
                            "room_name": "範囲外会場",
                        },
                        files={
                            "image": (
                                "capture.jpg",
                                b"\xff\xd8\xfftest",
                                "image/jpeg",
                            )
                        },
                    )
                    self.assertEqual(response.status_code, 422)
                    self.assertEqual(
                        response.json()["detail"],
                        "location_id is out of range",
                    )

    def test_submit_process_and_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            previous = {
                "CROWDED_DATA_DIR": os.environ.get("CROWDED_DATA_DIR"),
                "CROWDED_API_KEY": os.environ.get("CROWDED_API_KEY"),
                "CROWDED_DETECTOR": os.environ.get("CROWDED_DETECTOR"),
            }
            os.environ["CROWDED_DATA_DIR"] = directory
            os.environ["CROWDED_API_KEY"] = "test-key-1234567"
            os.environ["CROWDED_DETECTOR"] = "mock"
            try:
                from crowded_backend.main import app

                with TestClient(app) as client:
                    unauthorized = client.get("/api/v1/rooms/snapshot")
                    self.assertEqual(unauthorized.status_code, 401)

                    accepted = client.post(
                        "/api/v1/observations",
                        headers={"X-API-Key": "test-key-1234567"},
                        data={"device_id": "1", "room_name": "情報工学科"},
                        files={"image": ("capture.jpg", b"\xff\xd8\xfftest", "image/jpeg")},
                    )
                    self.assertEqual(accepted.status_code, 202)

                    rooms = []
                    deadline = time.monotonic() + 2
                    while time.monotonic() < deadline:
                        response = client.get(
                            "/api/v1/rooms/snapshot",
                            headers={"X-API-Key": "test-key-1234567"},
                        )
                        rooms = response.json()["rooms"]
                        if rooms:
                            break
                        time.sleep(0.01)
                    self.assertEqual(rooms[0]["room_name"], "情報工学科")
                    self.assertEqual(rooms[0]["person_count"], 0)
            finally:
                for name, value in previous.items():
                    if value is None:
                        os.environ.pop(name, None)
                    else:
                        os.environ[name] = value


if __name__ == "__main__":
    unittest.main()
