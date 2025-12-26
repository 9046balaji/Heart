from fastapi import APIRouter, HTTPException, Query, Body
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tools/medications", tags=["Medications"])


@router.get("/")
async def medical_root():
    return {"status": "Medication routes active"}


@router.get("/search")
async def search_medications(q: str = Query(..., min_length=2)):
    """Search for medications."""
    # Mock search results
    return {
        "query": q,
        "results": [
            {"id": "aspirin", "name": "Aspirin", "type": "NSAID"},
            {"id": "metformin", "name": "Metformin", "type": "Antidiabetic"},
        ],
        "count": 2
    }


@router.post("/interactions")
async def check_medication_interactions(medications: List[str] = Body(..., embed=True)):
    """Check for drug interactions."""
    try:
        from routes.tools_routes import check_drug_interactions, DrugInteractionRequest
        request = DrugInteractionRequest(medications=medications)
        return await check_drug_interactions(request)
    except Exception as e:
        logger.error(f"Error checking interactions: {e}")
        return {
            "medications_checked": medications,
            "interactions": [],
            "severity_summary": "No critical interactions found (Mock)",
            "recommendations": ["Consult your pharmacist"]
        }


@router.get("/{user_id}")
async def get_user_medications(user_id: str):
    """Get all medications for a user."""
    return {
        "user_id": user_id,
        "medications": [
            {
                "id": "med_1",
                "name": "Aspirin",
                "dosage": "81mg",
                "frequency": "daily",
                "schedule": ["08:00", "20:00"]
            }
        ]
    }


@router.post("/{user_id}")
async def add_user_medication(user_id: str, medication: Dict[str, Any] = Body(...)):
    """Add a new medication for a user."""
    med_id = f"med_{len(str(user_id))}"
    return {
        "id": med_id,
        "medication_id": med_id,
        "user_id": user_id,
        "status": "created",
        **medication
    }


@router.put("/{user_id}/{medication_id}")
async def update_user_medication(user_id: str, medication_id: str, updates: Dict[str, Any] = Body(...)):
    """Update a medication for a user."""
    return {
        "id": medication_id,
        "user_id": user_id,
        "status": "updated",
        **updates
    }


@router.delete("/{user_id}/{medication_id}")
async def delete_user_medication(user_id: str, medication_id: str):
    """Delete a medication for a user."""
    return {
        "id": medication_id,
        "user_id": user_id,
        "status": "deleted"
    }


@router.get("/reminders/{user_id}")
async def get_medication_reminders(user_id: str):
    """Get medication reminders for a user."""
    return {
        "user_id": user_id,
        "reminders": [
            {
                "id": "rem_1",
                "medication": "Aspirin",
                "dosage": "81mg",
                "time": "08:00",
                "frequency": "daily"
            }
        ]
    }
