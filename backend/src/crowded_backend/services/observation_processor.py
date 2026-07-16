from __future__ import annotations

import logging

from crowded_backend.inference.person_detector import PersonDetector
from crowded_backend.schemas import Observation
from crowded_backend.storage.csv_store import CsvStore


LOGGER = logging.getLogger(__name__)


class ObservationProcessor:
    def __init__(self, detector: PersonDetector, store: CsvStore) -> None:
        self.detector = detector
        self.store = store

    def process(self, observation: Observation) -> int:
        person_count = self.detector.count(observation.image)
        changed = self.store.record(
            device_id=observation.device_id,
            room_name=observation.room_name,
            person_count=person_count,
            observed_at=observation.received_at,
        )
        LOGGER.info(
            "processed device_id=%d person_count=%d room_name_changed=%s",
            observation.device_id,
            person_count,
            changed,
        )
        return person_count

