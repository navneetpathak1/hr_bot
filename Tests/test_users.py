
import pytest
from httpx import AsyncClient

from Tests.conftest import register_user, login_user, auth_header

# REGISTER
# 1. create and pass
# 2. duplicate email
# 3. duplicate username
# 4. password too short
# 5. username too short
# 6. invalid email
class TestRegister:

    @pytest.mark.asyncio
    async def test_register_success(self, client: AsyncClient):
        """Happy-path: new user is created, 201 returned with token and user."""
        response = await client.post(
            "/api/v1/register",
            json={
                "username": "alice",
                "email": "alice@example.com",
                "password": "securepass",
            },
        )
        assert response.status_code == 201
        body = response.json()

        # Auth response shape
        assert "access_token" in body
        assert body["token_type"] == "bearer"
        assert isinstance(body["access_token"], str)
        assert len(body["access_token"]) > 0

        # User sub-object
        user = body["user"]
        assert user["username"] == "alice"
        assert user["email"] == "alice@example.com"
        assert "id" in user
        assert "password" not in user  # password must NOT be exposed

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client: AsyncClient):
        """Registering with an already-used email returns 409 Conflict."""
        payload = {
            "username": "bob",
            "email": "bob@example.com",
            "password": "pass1234",
        }
        r1 = await client.post("/api/v1/register", json=payload)
        assert r1.status_code == 201

        payload["username"] = "bob2"  # different username, same email
        r2 = await client.post("/api/v1/register", json=payload)
        assert r2.status_code == 409
        assert "already exists" in r2.json()["message"].lower()

    @pytest.mark.asyncio
    async def test_register_duplicate_username(self, client: AsyncClient):
        """Registering with an already-used username returns 409 Conflict."""
        payload = {
            "username": "carol",
            "email": "carol@example.com",
            "password": "pass1234",
        }
        r1 = await client.post("/api/v1/register", json=payload)
        assert r1.status_code == 201

        payload["email"] = "carol2@example.com"  # different email, same username
        r2 = await client.post("/api/v1/register", json=payload)
        assert r2.status_code == 409

    @pytest.mark.asyncio
    async def test_register_password_too_short(self, client: AsyncClient):
        """Password shorter than 4 characters must be rejected with 422."""
        response = await client.post(
            "/api/v1/register",
            json={
                "username": "dave",
                "email": "dave@example.com",
                "password": "abc",   # 3 chars – below min_length=4
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_username_too_short(self, client: AsyncClient):
        """Username shorter than 3 characters must be rejected with 422."""
        response = await client.post(
            "/api/v1/register",
            json={
                "username": "ab",   # 2 chars – below min_length=3
                "email": "ab@example.com",
                "password": "validpass",
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_invalid_email(self, client: AsyncClient):
        """Malformed email must be rejected with 422."""
        response = await client.post(
            "/api/v1/register",
            json={
                "username": "eve",
                "email": "not-an-email",
                "password": "validpass",
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_missing_fields(self, client: AsyncClient):
        """Omitting required fields must be rejected with 422."""
        # Missing password
        response = await client.post(
            "/api/v1/register",
            json={
                "username": "frank",
                "email": "frank@example.com",
            },
        )
        assert response.status_code == 422

# Login
# 1. using username
# 2. using email
# 3. wrong username

class TestLogin:

    @pytest.mark.asyncio
    async def test_login_with_username(self, client: AsyncClient):
        """Login using username in form field returns 200 + access_token."""
        await register_user(client, username="grace", email="grace@example.com", password="mypassword")

        response = await client.post(
            "/api/v1/login",
            data={"username": "grace", "password": "mypassword"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert response.status_code == 200
        body = response.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"
        assert body["user"]["username"] == "grace"

    @pytest.mark.asyncio
    async def test_login_with_email(self, client: AsyncClient):
        """Login using email in the username form field returns 200 + access_token."""
        await register_user(client, username="heidi", email="heidi@example.com", password="mypassword")

        response = await client.post(
            "/api/v1/login",
            data={"username": "heidi@example.com", "password": "mypassword"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert response.status_code == 200
        body = response.json()
        assert "access_token" in body
        assert body["user"]["email"] == "heidi@example.com"

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client: AsyncClient):
        """Logging in with a username that doesn't exist must return 404."""
        response = await client.post(
            "/api/v1/login",
            data={"username": "ghost_user_xyz", "password": "somepass"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert response.status_code == 404
        assert "not found" in response.json()["message"].lower()


# PROFILE – protected GET /api/v1/profile
# 1. valid
# 2. without token
# 3. wrong token
class TestProfile:

    @pytest.mark.asyncio
    async def test_profile_authenticated(self, client: AsyncClient, auth_headers: dict):
        """/profile returns 200 and the correct user data for a valid token."""
        response = await client.get("/api/v1/profile", headers=auth_headers)
        assert response.status_code == 200
        body = response.json()
        assert "username" in body
        assert "email" in body
        assert body["message"] == "You are authenticated!"

    @pytest.mark.asyncio
    async def test_profile_no_token(self, client: AsyncClient):
        """/profile without a token must return 401."""
        response = await client.get("/api/v1/profile")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_profile_invalid_token(self, client: AsyncClient):
        """/profile with a tampered / garbage token must return 401."""
        response = await client.get(
            "/api/v1/profile",
            headers={"Authorization": "Bearer this.is.not.a.valid.jwt"},
        )
        assert response.status_code == 401

# uv run pytest .\Tests\test_users.py -v
# uv run pytest --disable-plugin-autoload -p pytest_asyncio.plugin .\Tests\test_users.py -v