"""
Testes do segundo security audit (achados 1-9, 11-16, 19-20).
"""
import pytest
from httpx import AsyncClient

BASE = "/auth"


async def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_email_normalizado_lowercase(client: AsyncClient):
    """Email é salvo em lowercase — defesa contra account takeover."""
    r = await client.post(f"{BASE}/register", json={
        "username": "upper_user",
        "email": "Test@Email.COM",
        "password": "secret123",
    })
    assert r.status_code == 201

    # Login com versão lowercase deve funcionar
    r2 = await client.post(f"{BASE}/login", json={
        "email_or_username": "test@email.com",
        "password": "secret123",
    })
    assert r2.status_code == 200


@pytest.mark.asyncio
async def test_email_duplicado_case_insensitive(client: AsyncClient):
    """Registrar com email em case diferente falha (case-insensitive check)."""
    r1 = await client.post(f"{BASE}/register", json={
        "username": "user1",
        "email": "Test@Email.com",
        "password": "secret123",
    })
    assert r1.status_code == 201

    r2 = await client.post(f"{BASE}/register", json={
        "username": "user2",
        "email": "test@email.com",  # mesmo email, case diferente
        "password": "secret123",
    })
    assert r2.status_code == 409
    assert "Email" in r2.json()["detail"]


@pytest.mark.asyncio
async def test_ready_nao_vaza_info(client: AsyncClient):
    """/ready retorna mensagem genérica mesmo se o DB falhar."""
    r = await client.get("/ready")
    # Em teste, DB tá funcionando, então deve dar 200
    assert r.status_code == 200
    body = r.json()
    assert body == {"status": "ready", "database": "ok"}


@pytest.mark.asyncio
async def test_update_me_data_invalida_retorna_400(client: AsyncClient):
    """update_me com data inválida retorna 400 (não 500)."""
    r = await client.post(f"{BASE}/register", json={
        "username": "data_user",
        "email": "data@test.com",
        "password": "secret123",
    })
    token = r.json()["access_token"]

    # Data inválida
    r2 = await client.patch(
        "/users/me",
        json={"nascimento": "not-a-date"},
        headers=await auth_header(token),
    )
    assert r2.status_code == 400
    assert "Data" in r2.json()["detail"] or "data" in r2.json()["detail"]


@pytest.mark.asyncio
async def test_url_s3_bloqueia_javascript(client: AsyncClient):
    """url_s3 com javascript: é rejeitado (XSS prevention)."""
    r = await client.post(f"{BASE}/register", json={
        "username": "xss_user",
        "email": "xss@test.com",
        "password": "secret123",
    })
    token = r.json()["access_token"]

    r2 = await client.patch(
        "/users/me",
        json={"foto_url_s3": "javascript:alert(1)"},
        headers=await auth_header(token),
    )
    assert r2.status_code == 422


@pytest.mark.asyncio
async def test_url_s3_bloqueia_data_html(client: AsyncClient):
    """url_s3 com data:text/html é rejeitado."""
    r = await client.post(f"{BASE}/register", json={
        "username": "data_url_user",
        "email": "dataurl@test.com",
        "password": "secret123",
    })
    token = r.json()["access_token"]

    r2 = await client.patch(
        "/users/me",
        json={"foto_url_s3": "data:text/html,<script>alert(1)</script>"},
        headers=await auth_header(token),
    )
    assert r2.status_code == 422


@pytest.mark.asyncio
async def test_soft_delete_user(client: AsyncClient):
    """DELETE /users/me faz soft delete (LGPD/GDPR)."""
    r = await client.post(f"{BASE}/register", json={
        "username": "delete_me",
        "email": "delete@test.com",
        "password": "secret123",
    })
    access = r.json()["access_token"]
    refresh = r.json()["refresh_token"]

    # Soft delete
    r2 = await client.delete("/users/me", headers=await auth_header(access))
    assert r2.status_code == 200

    # Login com a conta deve falhar (conta "deletada")
    r3 = await client.post(f"{BASE}/login", json={
        "email_or_username": "delete_me",
        "password": "secret123",
    })
    assert r3.status_code == 401

    # Refresh com o token antigo também deve falhar (revogado)
    r4 = await client.post(f"{BASE}/refresh", json={"refresh_token": refresh})
    assert r4.status_code == 401


@pytest.mark.asyncio
async def test_user_deletado_nao_aparece(client: AsyncClient):
    """User soft-deletado não aparece em GET /users/{username}."""
    r = await client.post(f"{BASE}/register", json={
        "username": "ghost_user",
        "email": "ghost@test.com",
        "password": "secret123",
    })
    access = r.json()["access_token"]

    # Outro user tenta ver o ghost_user
    await client.post(f"{BASE}/register", json={
        "username": "viewer",
        "email": "viewer@test.com",
        "password": "secret123",
    })
    viewer_token = (await client.post(f"{BASE}/login", json={
        "email_or_username": "viewer",
        "password": "secret123",
    })).json()["access_token"]

    # Antes de deletar, viewer vê
    r_view = await client.get(
        "/users/ghost_user", headers=await auth_header(viewer_token)
    )
    assert r_view.status_code == 200

    # Ghost deleta a si mesmo
    r_del = await client.delete("/users/me", headers=await auth_header(access))
    assert r_del.status_code == 200

    # Depois de deletar, viewer NÃO vê mais
    r_view2 = await client.get(
        "/users/ghost_user", headers=await auth_header(viewer_token)
    )
    assert r_view2.status_code == 404
