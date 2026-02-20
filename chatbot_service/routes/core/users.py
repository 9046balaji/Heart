"""
User / Medications Routes
=========================
CRUD endpoints for user medication management.
Endpoints:
    GET    /users/{user_id}/medications
    POST   /users/{user_id}/medications
    PUT    /users/{user_id}/medications/{medication_id}
    DELETE /users/{user_id}/medications/{medication_id}
"""

import logging
import uuid
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("users")

router = APIRouter()


# ---------------------------------------------------------------------------
# In-memory store (production would use PostgreSQL)
# ---------------------------------------------------------------------------

_medication_store: dict = {}  # user_id -> [medications]


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class MedicationBase(BaseModel):
    name: str
    dosage: str
    schedule: List[str] = Field(default_factory=list, description="e.g. ['08:00', '20:00']")
    frequency: str = "daily"
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    notes: Optional[str] = None


class MedicationCreate(MedicationBase):
    pass


class MedicationUpdate(BaseModel):
    name: Optional[str] = None
    dosage: Optional[str] = None
    schedule: Optional[List[str]] = None
    frequency: Optional[str] = None
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    notes: Optional[str] = None


class MedicationResponse(MedicationBase):
    id: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/{user_id}/medications", response_model=List[MedicationResponse])
async def get_medications(user_id: str):
    """Get all medications for a user."""
    meds = _medication_store.get(user_id, [])
    return meds


@router.post("/{user_id}/medications", response_model=MedicationResponse, status_code=201)
async def add_medication(user_id: str, medication: MedicationCreate):
    """Add a new medication for a user."""
    if user_id not in _medication_store:
        _medication_store[user_id] = []

    med = MedicationResponse(
        id=str(uuid.uuid4()),
        name=medication.name,
        dosage=medication.dosage,
        schedule=medication.schedule,
        frequency=medication.frequency,
        startDate=medication.startDate or datetime.utcnow().strftime("%Y-%m-%d"),
        endDate=medication.endDate,
        notes=medication.notes,
    )
    _medication_store[user_id].append(med.dict())
    logger.info(f"Medication added for user {user_id}: {medication.name}")
    return med


@router.put("/{user_id}/medications/{medication_id}", response_model=MedicationResponse)
async def update_medication(user_id: str, medication_id: str, update: MedicationUpdate):
    """Update an existing medication."""
    meds = _medication_store.get(user_id, [])
    for i, med in enumerate(meds):
        if med["id"] == medication_id:
            update_data = update.dict(exclude_unset=True)
            meds[i] = {**med, **update_data}
            logger.info(f"Medication updated for user {user_id}: {medication_id}")
            return MedicationResponse(**meds[i])

    raise HTTPException(status_code=404, detail=f"Medication {medication_id} not found")


@router.delete("/{user_id}/medications/{medication_id}")
async def delete_medication(user_id: str, medication_id: str):
    """Delete a medication."""
    meds = _medication_store.get(user_id, [])
    for i, med in enumerate(meds):
        if med["id"] == medication_id:
            meds.pop(i)
            logger.info(f"Medication deleted for user {user_id}: {medication_id}")
            return {"message": f"Medication {medication_id} deleted successfully"}

    raise HTTPException(status_code=404, detail=f"Medication {medication_id} not found")
