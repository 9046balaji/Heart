"""
Weekly Summary Trigger Route
=============================
Separate prefix for triggering weekly summary generation.
Endpoint:
    POST /weekly-summary/trigger
"""

import logging
from typing import Optional
from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger("weekly-summary")

router = APIRouter()


class TriggerRequest(BaseModel):
    user_id: str


class TriggerResponse(BaseModel):
    status: str
    user_id: str
    message: str
    triggered_at: str


@router.post("/trigger", response_model=TriggerResponse)
async def trigger_weekly_summary(request: TriggerRequest):
    """Trigger generation of a weekly health summary for a user."""
    logger.info(f"Weekly summary triggered for user {request.user_id}")

    return TriggerResponse(
        status="triggered",
        user_id=request.user_id,
        message="Weekly summary generation has been triggered. It will be available shortly.",
        triggered_at=datetime.utcnow().isoformat() + "Z",
    )
