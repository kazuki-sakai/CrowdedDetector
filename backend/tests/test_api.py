from __future__ import annotations

import os
import tempfile
import time
import unittest

try:
    from fastapi.testclient import TestClient
except ImportError:
    TestClient = None


@unittest.skipIf(TestClient is None, "FastAPI test dependencies are not installed")
class ApiTest(unittest.TestCase):
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
