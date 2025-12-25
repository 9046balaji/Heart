from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import timedelta
import logging

from core.security import (
    SecurityManager,
    get_current_user,
    hash_password,
    verify_password,
    ACCESS_TOKEN_EXPIRE_MINUTES
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
logger = logging.getLogger(__name__)

security_manager = SecurityManager()

# Mock user database
MOCK_USERS_DB = {}

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    refresh_token: Optional[str] = None

class UserResponse(BaseModel):
    id: str
    email: EmailStr
    name: str

@router.post("/register", response_model=Token)
async def register(user: UserCreate):
    if user.email in MOCK_USERS_DB:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    hashed_password = hash_password(user.password)
    user_id = str(len(MOCK_USERS_DB) + 1)
    
    user_data = {
        "id": user_id,
        "email": user.email,
        "name": user.name,
        "hashed_password": hashed_password
    }
    
    MOCK_USERS_DB[user.email] = user_data
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security_manager.create_access_token(
        data={"sub": user.email, "user_id": user_id},
        expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/login", response_model=Token)
async def login(user_credentials: UserLogin):
    user = MOCK_USERS_DB.get(user_credentials.email)
    
    if not user or not verify_password(user_credentials.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security_manager.create_access_token(
        data={"sub": user["email"], "user_id": user["id"]},
        expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: dict = Depends(get_current_user)):
    user_email = current_user.get("sub")
    user = MOCK_USERS_DB.get(user_email)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "id": user["id"],
        "email": user["email"],
        "name": user["name"]
    }

@router.post("/refresh", response_model=Token)
async def refresh_token(current_user: dict = Depends(get_current_user)):
    # In a real implementation, we would verify the refresh token
    # For now, we just issue a new access token based on the current user
    user_email = current_user.get("sub")
    user_id = current_user.get("user_id")
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security_manager.create_access_token(
        data={"sub": user_email, "user_id": user_id},
        expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/logout")
async def logout():
    return {"message": "Successfully logged out"}
