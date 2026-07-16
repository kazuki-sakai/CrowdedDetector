from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from crowded_backend.api.security import require_api_key


router = APIRouter(prefix="/api/v1", tags=["snapshots"])


@router.get("/rooms/snapshot", dependencies=[Depends(require_api_key)])
def room_snapshot(request: Request) -> dict[str, object]:
    return request.app.state.store.snapshot()

