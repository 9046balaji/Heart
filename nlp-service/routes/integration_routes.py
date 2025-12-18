from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def integration_root():
    return {"status": "Integration routes active"}
