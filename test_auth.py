"""
Testes do fluxo de autenticação.

Cobre:
- Registro com sucesso
- Registro com email duplicado (409)
- Registro com username duplicado (409)
- Registro com username inválido (422)
- Login com sucesso
- Login com senha errada (401)
- Login com username (em vez de email)
- /auth/me com token válido
- /auth/me sem token (401)
"""

import pytest
from httpx import AsyncClient

BASE = "/auth"


# ============================================================
# /auth/register
# ============================================================
@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    """Registro válido retorna 201 + tokens."""
    response = await client.post(
        f"{BASE}/register",
        json={
            "username": "sarah.beats",
            "email": "sarah@beats.com",
            "password": "secret123",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    """Email duplicado retorna 409."""
    payload = {
        "username": "user1",
        "email": "same@email.com",
        "password": "secret123",
    }
    await client.post(f"{BASE}/register", json=payload)

    response = await client.post(
        f"{BASE}/register",
        json={**payload, "username": "user2"},
    )
    assert response.status_code == 409
    assert "Email" in response.json()["detail"]


@pytest.mark.asyncio
async def test_register_duplicate_username(client: AsyncClient):
    """Username duplicado retorna 409."""
    payload = {
        "username": "sameuser",
        "email": "user1@email.com",
        "password": "secret123",
    }
    await client.post(f"{BASE}/register", json=payload)

    response = await client.post(
        f"{BASE}/register",
        json={**payload, "email": "user2@email.com"},
    )
    assert response.status_code == 409
    assert "Username" in response.json()["detail"]


@pytest.mark.asyncio
async def test_register_invalid_username(client: AsyncClient):
    """Username com caracteres inválidos retorna 422."""
    response = await client.post(
        f"{BASE}/register",
        json={
            "username": "user@inválido!",
            "email": "test@email.com",
            "password": "secret123",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_short_password(client: AsyncClient):
    """Senha com menos de 8 chars retorna 422."""
    response = await client.post(
        f"{BASE}/register",
        json={
            "username": "validuser",
            "email": "test@email.com",
            "password": "short",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_invalid_email(client: AsyncClient):
    """Email inválido retorna 422."""
    response = await client.post(
        f"{BASE}/register",
        json={
            "username": "validuser",
            "email": "not-an-email",
            "password": "secret123",
        },
    )
    assert response.status_code == 422


# ============================================================
# /auth/login
# ============================================================
@pytest.mark.asyncio
async def test_login_with_email_success(client: AsyncClient):
    """Login com email retorna 200 + tokens."""
    await client.post(
        f"{BASE}/register",
        json={
            "username": "sarah.beats",
            "email": "sarah@beats.com",
            "password": "secret123",
        },
    )

    response = await client.post(
        f"{BASE}/login",
        json={"email_or_username": "sarah@beats.com", "password": "secret123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data


@pytest.mark.asyncio
async def test_login_with_username_success(client: AsyncClient):
    """Login com username também funciona."""
    await client.post(
        f"{BASE}/register",
        json={
            "username": "sarah.beats",
            "email": "sarah@beats.com",
            "password": "secret123",
        },
    )

    response = await client.post(
        f"{BASE}/login",
        json={"email_or_username": "sarah.beats", "password": "secret123"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    """Senha errada retorna 401."""
    await client.post(
        f"{BASE}/register",
        json={
            "username": "sarah",
            "email": "sarah@beats.com",
            "password": "secret123",
        },
    )

    response = await client.post(
        f"{BASE}/login",
        json={"email_or_username": "sarah@beats.com", "password": "wrong"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient):
    """Usuário inexistente retorna 401 (não 404, pra não vazar info)."""
    response = await client.post(
        f"{BASE}/login",
        json={"email_or_username": "naoexiste@email.com", "password": "qualquer"},
    )
    assert response.status_code == 401


# ============================================================
# /auth/me
# ============================================================
@pytest.mark.asyncio
async def test_me_with_valid_token(client: AsyncClient):
    """Token válido retorna dados do usuário."""
    register = await client.post(
        f"{BASE}/register",
        json={
            "username": "sarah",
            "email": "sarah@beats.com",
            "password": "secret123",
        },
    )
    token = register.json()["access_token"]

    response = await client.get(
        f"{BASE}/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "sarah"
    assert data["email"] == "sarah@beats.com"
    assert "senha_hash" not in data


@pytest.mark.asyncio
async def test_me_without_token(client: AsyncClient):
    """Sem token retorna 401."""
    response = await client.get(f"{BASE}/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_with_invalid_token(client: AsyncClient):
    """Token inválido retorna 401."""
    response = await client.get(
        f"{BASE}/me",
        headers={"Authorization": "Bearer invalid.token.here"},
    )
    assert response.status_code == 401


# ============================================================
# Health
# ============================================================
@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    """Health check retorna 200."""
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
