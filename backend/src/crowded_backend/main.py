from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request

from crowded_backend.api.observations import router as observations_router
from crowded_backend.api.snapshots import router as snapshots_router
from crowded_backend.inference.person_detector import (
    MockPersonDetector,
    RandomPersonDetector,
    YoloPersonDetector,
)
from crowded_backend.services.observation_processor import ObservationProcessor
from crowded_backend.settings import Settings
from crowded_backend.storage.csv_store import CsvStore


LOGGER = logging.getLogger(__name__)


def _make_detector(settings: Settings):
    if settings.detector == "yolo":
        return YoloPersonDetector(
            model_name=settings.yolo_model,
            device=settings.yolo_device,
            confidence=settings.yolo_confidence,
            image_size=settings.yolo_image_size,
            warmup_width=settings.yolo_warmup_width,
            warmup_height=settings.yolo_warmup_height,
        )
    if settings.detector == "random":
        return RandomPersonDetector(
            min_count=settings.random_min_count,
            max_count=settings.random_max_count,
            seed=settings.random_seed,
        )
    return MockPersonDetector()


async def _worker(app: FastAPI) -> None:
    while True:
        observation = await app.state.queue.get()
        try:
            await asyncio.to_thread(app.state.processor.process, observation)
        except Exception:
            LOGGER.exception("failed to process device_id=%d", observation.device_id)
        finally:
            app.state.queue.task_done()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings.from_env()
    store = CsvStore(settings.data_dir, settings.max_devices)
    app.state.settings = settings
    app.state.store = store
    app.state.queue = asyncio.Queue(maxsize=settings.queue_size)
    app.state.processor = ObservationProcessor(_make_detector(settings), store)
    worker_task = asyncio.create_task(_worker(app), name="observation-worker")
    app.state.worker_task = worker_task
    try:
        yield
    finally:
        worker_task.cancel()
        await asyncio.gather(worker_task, return_exceptions=True)


app = FastAPI(
    title="CrowdedDetector API",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(observations_router)
app.include_router(snapshots_router)


@app.get("/health", tags=["health"])
def health(request: Request) -> dict[str, object]:
    return {
        "status": "ok",
        "detector": request.app.state.settings.detector,
        "queue_depth": request.app.state.queue.qsize(),
        "queue_capacity": request.app.state.settings.queue_size,
    }
