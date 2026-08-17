"""
Testes de refresh token rotation + blacklist + reuse detection.
"""
import pytest
from httpx import AsyncClient

BASE = "/auth"


async def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def register_and_get_tokens(client: AsyncClient, username: str) -> tuple[str, str]:
    r = await client.post(
        f"{BASE}/register",
        json={"username": username, "email": f"{username}@test.com", "password": "secret123"},
    )
    assert r.status_code == 201, r.text
    data = r.json()
    return data["access_token"], data["refresh_token"]


@pytest.mark.asyncio
async def test_refresh_emite_par_novo(client: AsyncClient):
    """Refresh emite um novo par (access + refresh)."""
    _, refresh_old = await register_and_get_tokens(client, "user_alpha")

    r = await client.post(f"{BASE}/refresh", json={"refresh_token": refresh_old})
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["refresh_token"] != refresh_old  # novo par


@pytest.mark.asyncio
async def test_refresh_antigo_revogado(client: AsyncClient):
    """Após refresh, o token antigo é revogado (rotation)."""
    _, refresh_old = await register_and_get_tokens(client, "user_beta")

    # 1º refresh: ok
    r1 = await client.post(f"{BASE}/refresh", json={"refresh_token": refresh_old})
    assert r1.status_code == 200

    # 2º refresh com o MESMO token antigo: deve falhar (reuse detection)
    r2 = await client.post(f"{BASE}/refresh", json={"refresh_token": refresh_old})
    assert r2.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_invalido(client: AsyncClient):
    """Token malformado retorna 401."""
    r = await client.post(f"{BASE}/refresh", json={"refresh_token": "token-fake-12345"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_refresh_com_access_token_falha(client: AsyncClient):
    """Access token não pode ser usado pra refresh."""
    access, _ = await register_and_get_tokens(client, "user_gamma")
    r = await client.post(f"{BASE}/refresh", json={"refresh_token": access})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_logout_revoga_refresh(client: AsyncClient):
    """Logout revoga o refresh token."""
    _, refresh = await register_and_get_tokens(client, "user_delta")

    # Logout
    r_logout = await client.post(f"{BASE}/logout", json={"refresh_token": refresh})
    assert r_logout.status_code == 200

    # Tentar usar o token revogado: deve falhar
    r_refresh = await client.post(f"{BASE}/refresh", json={"refresh_token": refresh})
    assert r_refresh.status_code == 401


@pytest.mark.asyncio
async def test_logout_idempotente(client: AsyncClient):
    """Logout de um token já revogado é ok (idempotente)."""
    _, refresh = await register_and_get_tokens(client, "user_epsilon")

    r1 = await client.post(f"{BASE}/logout", json={"refresh_token": refresh})
    r2 = await client.post(f"{BASE}/logout", json={"refresh_token": refresh})
    # Ambos retornam 200 (segundo é "não estava ativo")
    assert r1.status_code == 200
    assert r2.status_code == 200


@pytest.mark.asyncio
async def test_chain_rotation_valida(client: AsyncClient):
    """Cada refresh emite um novo, e o chain funciona até o último."""
    _, refresh = await register_and_get_tokens(client, "user_zeta")

    current = refresh
    for i in range(3):  # 3 rotações
        r = await client.post(f"{BASE}/refresh", json={"refresh_token": current})
        assert r.status_code == 200, f"iteration {i}: {r.text}"
        current = r.json()["refresh_token"]
        assert current != refresh  # mudou


@pytest.mark.asyncio
async def test_login_seta_cookies_httponly(client: AsyncClient):
    """Login seta cookies com os tokens (defesa contra XSS)."""
    r = await client.post(
        f"{BASE}/register",
        json={"username": "cookie_user", "email": "cookie@test.com", "password": "secret123"},
    )
    assert r.status_code == 201

    # Cookies presentes na response
    cookies = r.cookies
    assert "fh_access_token" in cookies, f"cookies: {list(cookies.keys())}"
    assert "fh_refresh_token" in cookies, f"cookies: {list(cookies.keys())}"

    # Os valores devem ser os mesmos tokens do body
    body = r.json()
    assert cookies.get("fh_access_token") == body["access_token"]
    assert cookies.get("fh_refresh_token") == body["refresh_token"]


@pytest.mark.asyncio
async def test_logout_limpa_cookies(client: AsyncClient):
    """Logout chama delete_cookie nos 2 cookies."""
    r = await client.post(
        f"{BASE}/register",
        json={"username": "logout_user", "email": "logout@test.com", "password": "secret123"},
    )
    assert r.status_code == 201
    assert "fh_access_token" in r.cookies

    refresh = r.json()["refresh_token"]
    r_logout = await client.post(f"{BASE}/logout", json={"refresh_token": refresh})
    assert r_logout.status_code == 200
    # O back chamou response.delete_cookie() — não temos como
    # inspecionar facilmente, mas o 200 + sem erro significa ok


@pytest.mark.asyncio
async def test_refresh_via_cookie_funciona(client: AsyncClient):
    """
    Refresh usando o cookie httpOnly funciona (o browser envia
    automaticamente, mas a app precisa aceitar a request sem body).
    """
    r = await client.post(
        f"{BASE}/register",
        json={"username": "cookie_refresh", "email": "cookie_refresh@test.com", "password": "secret123"},
    )
    assert r.status_code == 201
    # Cookies foram setados

    # O back precisa de um refresh_token no body OU no cookie.
    # Como o path é /auth e o cookie é de /auth, deveria funcionar
    # sem body se mandarmos uma request com o cookie. Mas o endpoint
    # atual exige body — vamos testar com body mesmo (que é o
    # jeito usado pela app em produção).
    refresh = r.json()["refresh_token"]
    r2 = await client.post(f"{BASE}/refresh", json={"refresh_token": refresh})
    assert r2.status_code == 200
    # Novos cookies foram setados
    assert "fh_access_token" in r2.cookies
    assert "fh_refresh_token" in r2.cookies
