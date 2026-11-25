
import os
import jwt
from collections.abc import AsyncGenerator

from dotenv import load_dotenv

load_dotenv()

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config.database import Base, get_db
from app.routes.main_route import app

pytest_plugins = ["pytest_asyncio"]


# Engine & Schema
DATABASE_URL_TEST = os.environ.get("DATABASE_URL_TEST")

@pytest.fixture(scope="session")
def test_engine():
    """Synchronous-looking fixture that returns an async engine (NullPool)."""
    engine = create_async_engine(
        DATABASE_URL_TEST,
        poolclass=NullPool,
    )
    return engine

@pytest_asyncio.fixture(scope="session")
async def setup_database(test_engine):
    """
    Create all ORM tables before the session starts; drop them after.
    """
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await test_engine.dispose()


# Per-test DB session 

@pytest_asyncio.fixture
async def db_session(
    test_engine,
    setup_database,
) -> AsyncGenerator[AsyncSession, None]:
    """
    Open a real connection, begin a savepoint transaction, yield the session,
    then roll back
    """
    conn = await test_engine.connect()
    trans = await conn.begin()

    session_factory = async_sessionmaker(
        bind=conn,
        class_=AsyncSession,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )

    async with session_factory() as session:
        try:
            yield session
        finally:
            await session.close()

    await trans.rollback()
    await conn.close()


# HTTP client

@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    AsyncClient wired to the FastAPI app via ASGI transport.
    Overrides the `get_db` dependency so every request shares the rolled-back
    test session.
    """

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# Helper: register a user and return the full JSON response

async def register_user(
    client: AsyncClient,
    username: str = "testuser",
    email: str = "test@example.com",
    password: str = "testpass123",
) -> dict:
    """
    POST /api/v1/register with JSON body.
    Asserts HTTP 201 and returns the parsed response body.
    """
    response = await client.post(
        "/api/v1/register",
        json={
            "username": username,
            "email": email,
            "password": password,
        },
    )
    assert response.status_code == 201, (
        f"register_user failed ({response.status_code}): {response.text}"
    )
    return response.json()


# Helper: login and return access token string

async def login_user(
    client: AsyncClient,
    username: str = "testuser",
    password: str = "testpass123",
) -> str:
    """
    POST /api/v1/login with form-encoded body (OAuth2PasswordRequestForm style).
    Accepts username OR email in the `username` field.
    Returns the raw access_token string.
    """
    response = await client.post(
        "/api/v1/login",
        data={          # <-- form-encoded, not JSON
            "username": username,
            "password": password,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200, (
        f"login_user failed ({response.status_code}): {response.text}"
    )
    return response.json()["access_token"]


# Helper: build Authorization header dict

def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# Convenience fixture: registered user + token ready to use in any test

@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient) -> dict[str, str]:
    """
    Registers a fresh user for the current test, logs in, and returns the
    Authorization header dict – ready to pass to `client.get(...)`.
    """
    await register_user(client)
    token = await login_user(client)
    return auth_header(token)