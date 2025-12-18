from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def medical_root():
    return {"status": "Medical routes active"}
