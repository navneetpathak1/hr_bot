import os
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from typing import Annotated
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError
from fastapi.security import OAuth2PasswordBearer
from fastapi import Form
from dotenv import load_dotenv

load_dotenv()

JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGO = os.getenv("JWT_ALGO")

from app.schema.user_shema import UserCreate, UserLogin, AuthResponse
from app.models.user_models import User
from app.config.database import get_db
import jwt

router = APIRouter()
ph = PasswordHasher()
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="api/v1/login"
)

@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    response = await db.execute(
        select(User).where(User.email == user.email)
    )

    existing_email = response.scalar_one_or_none()

    response2 = await db.execute(
        select(User).where(User.username == user.username)
    )

    existing_username = response2.scalar_one_or_none()


    if existing_email or existing_username:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User already exists"
        )

    # Create a new user
    hash_password = ph.hash(user.password) 
    new_user = User(
        username=user.username,
        email=user.email,
        password = hash_password
    )

    db.add(new_user)

    try:
        await db.commit()
        await db.refresh(new_user)
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register user"
        )

    token = jwt.encode({"sub": str(new_user.id)}, JWT_SECRET, algorithm=JWT_ALGO)

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": new_user
    }

@router.post("/login", response_model=AuthResponse)
async def login(username: Annotated[str, Form()],
    password: Annotated[str, Form()], 
    db: Annotated[AsyncSession, Depends(get_db)]
    ):
    response = await db.execute(
        select(User).where(
            or_(
                User.username == username,
                User.email == username
            )
        )
        )

    user_exist = response.scalar_one_or_none()

    if not user_exist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    try:
        ph.verify(
            user_exist.password,
            password
        )

    except (VerifyMismatchError, VerificationError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username/email or password"
        )
    

    token = jwt.encode({"sub": str(user_exist.id)}, JWT_SECRET, algorithm=JWT_ALGO)

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user_exist
    }


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)]
):

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"}
    )

    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGO]
        )

        user_id = payload.get("sub")

        if user_id is None:
            raise credentials_exception

    except jwt.InvalidTokenError:
        raise credentials_exception

    response = await db.execute(
        select(User).where(User.id == int(user_id))
    )

    current_user = response.scalar_one_or_none()

    if current_user is None:
        raise credentials_exception

    return current_user


@router.get("/profile")
async def profile(
    current_user: Annotated[User, Depends(get_current_user)]
):
    return {
        "message": "You are authenticated!",
        "username": current_user.username,
        "email": current_user.email
    }
