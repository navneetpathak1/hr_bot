from fastapi import APIRouter, Depends, HTTPException, status
from schema.user_shema import UserCreate, UserResponse

from typing import Annotated

from config.database import get_db

router = APIRouter()

@router.get("/register")
def register(user: UserCreate):
    pass

