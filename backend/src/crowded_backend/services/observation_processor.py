from __future__ import annotations

import logging
from time import perf_counter

from crowded_backend.inference.person_detector import PersonDetector
from crowded_backend.schemas import Observation
from crowded_backend.storage.csv_store import CsvStore


LOGGER = logging.getLogger(__name__)


class ObservationProcessor:
    def __init__(self, detector: PersonDetector, store: CsvStore) -> None:
        self.detector = detector
        self.store = store

    def process(self, observation: Observation) -> int:
        inference_started = perf_counter()
        person_count = self.detector.count(observation.image)
        inference_seconds = perf_counter() - inference_started
        changed = self.store.record(
            device_id=observation.device_id,
            location_id=observation.location_id,
            room_name=observation.room_name,
            zone_name=observation.zone_name,
            person_count=person_count,
            observed_at=observation.received_at,
        )
        LOGGER.info(
            "processed device_id=%d location_id=%d zone_name=%r "
            "person_count=%d assignment_changed=%s inference_seconds=%.4f",
            observation.device_id,
            observation.location_id or observation.device_id,
            observation.zone_name,
            person_count,
            changed,
            inference_seconds,
        )
        return person_count
