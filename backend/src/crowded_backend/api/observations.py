from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status

from crowded_backend.api.security import require_api_key
from crowded_backend.schemas import Observation


router = APIRouter(prefix="/api/v1", tags=["observations"])


def _is_supported_image(data: bytes) -> bool:
    return (
        data.startswith(b"\xff\xd8\xff")
        or data.startswith(b"\x89PNG\r\n\x1a\n")
    )


@router.post(
    "/observations",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_api_key)],
)
async def submit_observation(
    request: Request,
    device_id: int = Form(...),
    room_name: str = Form(...),
    location_id: int | None = Form(default=None),
    zone_name: str = Form(default=""),
    image: UploadFile = File(...),
) -> dict[str, object]:
    settings = request.app.state.settings
    room_name = room_name.strip()
    location_id = device_id if location_id is None else location_id
    zone_name = zone_name.strip()
    if not 1 <= device_id <= settings.max_devices:
        raise HTTPException(status_code=422, detail="device_id is out of range")
    if not 1 <= location_id <= settings.max_locations:
        raise HTTPException(status_code=422, detail="location_id is out of range")
    if not room_name or len(room_name) > 100 or "\n" in room_name or "\r" in room_name:
        raise HTTPException(status_code=422, detail="invalid room_name")
    if len(zone_name) > 100 or "\n" in zone_name or "\r" in zone_name:
        raise HTTPException(status_code=422, detail="invalid zone_name")

    payload = await image.read(settings.max_image_bytes + 1)
    await image.close()
    if len(payload) > settings.max_image_bytes:
        raise HTTPException(status_code=413, detail="image is too large")
    if not _is_supported_image(payload):
        raise HTTPException(status_code=415, detail="only JPEG and PNG images are accepted")

    observation = Observation(
        device_id=device_id,
        room_name=room_name,
        image=payload,
        received_at=datetime.now(timezone.utc),
        location_id=location_id,
        zone_name=zone_name,
    )
    try:
        request.app.state.queue.put_nowait(observation)
    except asyncio.QueueFull as exc:
        raise HTTPException(status_code=503, detail="processing queue is full") from exc

    return {
        "accepted": True,
        "device_id": device_id,
        "location_id": location_id,
        "queue_depth": request.app.state.queue.qsize(),
    }
