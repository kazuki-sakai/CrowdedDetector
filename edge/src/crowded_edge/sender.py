from __future__ import annotations

import requests

from crowded_edge.settings import DeviceSettings


class ObservationSender:
    def __init__(self, settings: DeviceSettings) -> None:
        self.settings = settings
        self.session = requests.Session()
        self.session.headers.update({"X-API-Key": settings.api_token})

    def send(self, image: bytes) -> dict[str, object]:
        response = self.session.post(
            self.settings.backend_url,
            data={
                "device_id": str(self.settings.device_id),
                "location_id": str(self.settings.location_id),
                "room_name": self.settings.room_name,
                "zone_name": self.settings.zone_name,
            },
            files={"image": ("capture.jpg", image, "image/jpeg")},
            timeout=self.settings.timeout_seconds,
            verify=self.settings.verify_tls,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("backend returned an unexpected response")
        return payload

    def close(self) -> None:
        self.session.close()
