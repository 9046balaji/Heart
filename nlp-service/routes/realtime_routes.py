from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def realtime_root():
    return {"status": "Realtime routes active"}
