"""
Testes de segurança e regressão para bugs encontrados na auditoria.

Cobre:
- XSS via nome de alimento malicioso (validado no backend)
- SQL LIKE escape (% e _ no search)
- Bcrypt pré-hash (senhas longas)
- Token decode valida tipo (access/refresh)
- Data de consumo fora do range
- UserPublic duplicado (removido)
- Auth/me com refresh token rejeitado
"""

import pytest
from httpx import AsyncClient

from tests.test_dieta import register_and_login, create_approved_alimento

BASE = "/alimentos"
BASE_AUTH = "/auth"


# ============================================================
# XSS — nome de alimento malicioso
# ============================================================
@pytest.mark.asyncio
async def test_nome_alimento_com_html_nao_executa_xss(client: AsyncClient, test_db):
    """
    Nome do alimento pode conter HTML. Backend deve aceitar e armazenar
    literalmente — quem tem que escapar é o FRONTEND (que agora usa DOM).
    """
    headers = await register_and_login(client, test_db, "user1")
    payload = {
        "nome": "<script>alert('xss')</script>",
        "calorias": 100,
    }
    response = await client.post(BASE, json=payload, headers=headers)
    assert response.status_code == 201
    # Backend retorna o nome como veio
    assert response.json()["nome"] == "<script>alert('xss')</script>"

    # E o admin vê o mesmo nome quando lista pending
    admin_h = await register_and_login(client, test_db, "admin", is_admin=True)
    pending = await client.get(f"{BASE}/pending", headers=admin_h)
    assert any(
        a["nome"] == "<script>alert('xss')</script>"
        for a in pending.json()["items"]
    )


# ============================================================
# SQL LIKE escape
# ============================================================
@pytest.mark.asyncio
async def test_search_com_percent_nao_retorna_tudo(client: AsyncClient, test_db):
    """
    Se o user buscar '%', NÃO pode retornar todos os alimentos.
    Comportamento esperado: só itens que tenham literalmente '%' no nome.
    """
    admin_h = await register_and_login(client, test_db, "admin", is_admin=True)
    await create_approved_alimento(client, admin_h, "Arroz")
    await create_approved_alimento(client, admin_h, "Feijão")
    await create_approved_alimento(client, admin_h, "Macarrão")

    # Sem o escape, "%" no LIKE casaria com qualquer coisa
    response = await client.get(f"{BASE}?search=%25")  # %25 = '%' encoded
    data = response.json()
    # Espera retornar 0 ou só itens com '%' no nome
    for item in data["items"]:
        assert "%" in item["nome"], f"Item {item['nome']} não tem '%' mas apareceu na busca"


@pytest.mark.asyncio
async def test_search_com_underscore_nao_retorna_tudo(client: AsyncClient, test_db):
    """Mesmo problema com _ (wildcard do LIKE)."""
    admin_h = await register_and_login(client, test_db, "admin", is_admin=True)
    await create_approved_alimento(client, admin_h, "Arroz")
    await create_approved_alimento(client, admin_h, "Feijão")

    response = await client.get(f"{BASE}?search=_")
    data = response.json()
    for item in data["items"]:
        assert "_" in item["nome"]


# ============================================================
# Bcrypt pré-hash
# ============================================================
@pytest.mark.asyncio
async def test_senha_longa_funciona(client: AsyncClient, test_db):
    """Senha > 72 bytes deve funcionar com pré-hash SHA-256."""
    # 100 chars
    long_password = "a" * 100
    payload = {
        "username": "longpassuser",
        "email": "long@example.com",
        "password": long_password,
    }
    reg = await client.post(f"{BASE_AUTH}/register", json=payload)
    assert reg.status_code == 201

    # Login com a mesma senha (longa) deve funcionar
    login = await client.post(
        f"{BASE_AUTH}/login",
        json={"email_or_username": "longpassuser", "password": long_password},
    )
    assert login.status_code == 200


@pytest.mark.asyncio
async def test_senha_lunga_diferente_rejeita(client: AsyncClient, test_db):
    """Senha > 72 chars diferente não deve autenticar."""
    pwd1 = "a" * 100
    pwd2 = "b" * 100
    await client.post(
        f"{BASE_AUTH}/register",
        json={"username": "longpwd", "email": "lp@example.com", "password": pwd1},
    )
    login = await client.post(
        f"{BASE_AUTH}/login",
        json={"email_or_username": "longpwd", "password": pwd2},
    )
    assert login.status_code == 401


# ============================================================
# Token type validation
# ============================================================
@pytest.mark.asyncio
async def test_access_token_como_refresh_rejeita(client: AsyncClient, test_db):
    """Access token NÃO pode ser usado no /auth/refresh."""
    reg = await client.post(
        f"{BASE_AUTH}/register",
        json={"username": "tokentest", "email": "t@e.com", "password": "secret123"},
    )
    access = reg.json()["access_token"]

    # Tenta usar access token como refresh
    response = await client.post(
        f"{BASE_AUTH}/refresh", json={"refresh_token": access}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_como_access_rejeita(client: AsyncClient, test_db):
    """Refresh token NÃO pode ser usado em rotas autenticadas."""
    reg = await client.post(
        f"{BASE_AUTH}/register",
        json={"username": "tokentest2", "email": "t2@e.com", "password": "secret123"},
    )
    refresh = reg.json()["refresh_token"]

    # Tenta usar refresh token em /auth/me
    response = await client.get(
        f"{BASE_AUTH}/me",
        headers={"Authorization": f"Bearer {refresh}"},
    )
    assert response.status_code == 401


# ============================================================
# Data de consumo — range check
# ============================================================
@pytest.mark.asyncio
async def test_data_muito_no_passado_rejeita(client: AsyncClient, test_db):
    """Data > 365 dias atrás deve ser rejeitada."""
    admin_h = await register_and_login(client, test_db, "admin", is_admin=True)
    al = await create_approved_alimento(client, admin_h, "Arroz")

    user_h = await register_and_login(client, test_db, "user1")
    response = await client.post(
        "/alimentacao",
        json={
            "alimento_id": al["id"],
            "quantidade": 100,
            "refeicao": "almoco",
            "data": "2020-01-01",  # ~6 anos atrás
        },
        headers=user_h,
    )
    assert response.status_code == 422  # Pydantic validation


@pytest.mark.asyncio
async def test_data_no_futuro_rejeita(client: AsyncClient, test_db):
    """Data no futuro (> 1 dia) deve ser rejeitada."""
    admin_h = await register_and_login(client, test_db, "admin", is_admin=True)
    al = await create_approved_alimento(client, admin_h, "Arroz")

    user_h = await register_and_login(client, test_db, "user1")
    response = await client.post(
        "/alimentacao",
        json={
            "alimento_id": al["id"],
            "quantidade": 100,
            "refeicao": "almoco",
            "data": "2030-12-31",
        },
        headers=user_h,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_data_invalida_no_query_rejeita(client: AsyncClient, test_db):
    """GET com data malformada retorna 400."""
    user_h = await register_and_login(client, test_db, "user1")
    response = await client.get("/alimentacao?data=ontem", headers=user_h)
    assert response.status_code == 400


# ============================================================
# Não permitir inserir alimento pending
# ============================================================
@pytest.mark.asyncio
async def test_bloqueia_alimento_pending_no_log(client: AsyncClient, test_db):
    """Garantia extra: alimento pending não pode entrar no log (defesa em camadas)."""
    user_h = await register_and_login(client, test_db, "user1")
    created = await client.post(
        BASE, json={"nome": "Em análise"}, headers=user_h
    )
    al_id = created.json()["id"]

    response = await client.post(
        "/alimentacao",
        json={
            "alimento_id": al_id,
            "quantidade": 100,
            "refeicao": "almoco",
            "data": "2026-08-10",
        },
        headers=user_h,
    )
    assert response.status_code == 400


# ============================================================
# Email case-insensitive no login
# ============================================================
@pytest.mark.asyncio
async def test_login_email_case_insensitive(client: AsyncClient, test_db):
    """Login com email em qualquer case deve funcionar."""
    await client.post(
        f"{BASE_AUTH}/register",
        json={
            "username": "casetest",
            "email": "Sarah@Example.com",
            "password": "secret123",
        },
    )
    # Tenta logar com lowercase
    response = await client.post(
        f"{BASE_AUTH}/login",
        json={"email_or_username": "sarah@example.com", "password": "secret123"},
    )
    assert response.status_code == 200


# ============================================================
# Timing attack mitigation (smoke test — não mede tempo, só garante que não crasha)
# ============================================================
@pytest.mark.asyncio
async def test_login_com_user_inexistente_nao_vaza_info(client: AsyncClient, test_db):
    """Login com user inexistente deve dar 401 com mensagem genérica."""
    response = await client.post(
        f"{BASE_AUTH}/login",
        json={"email_or_username": "naoexiste@example.com", "password": "qualquer"},
    )
    assert response.status_code == 401
    # Mensagem genérica — não vaza se user existe
    assert "incorretos" in response.json()["detail"].lower()


# ============================================================
# Security headers
# ============================================================
@pytest.mark.asyncio
async def test_security_headers_present(client: AsyncClient):
    """Resposta da API deve trazer headers de segurança."""
    response = await client.get("/health")
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "geolocation=()" in response.headers.get("Permissions-Policy", "")


@pytest.mark.asyncio
async def test_cors_apenas_origens_permitidas(client: AsyncClient):
    """CORS deve restringir origens."""
    # Origem não listada
    response = await client.get(
        "/health",
        headers={"Origin": "https://malicious.com"},
    )
    # Access-Control-Allow-Origin não deve refletir a origem maliciosa
    allowed = response.headers.get("Access-Control-Allow-Origin", "")
    assert allowed != "https://malicious.com"


# ============================================================
# Validação de tamanho de strings
# ============================================================
@pytest.mark.asyncio
async def test_username_muito_curto_rejeita(client: AsyncClient):
    """Username < 3 chars é rejeitado."""
    response = await client.post(
        f"{BASE_AUTH}/register",
        json={
            "username": "ab",
            "email": "a@b.com",
            "password": "secret123",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_username_muito_longo_rejeita(client: AsyncClient):
    """Username > 50 chars é rejeitado."""
    response = await client.post(
        f"{BASE_AUTH}/register",
        json={
            "username": "a" * 51,
            "email": "a@b.com",
            "password": "secret123",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_email_muito_longo_rejeita(client: AsyncClient):
    """Email > 255 chars é rejeitado."""
    long_email = ("a" * 250) + "@b.com"  # 255 chars
    response = await client.post(
        f"{BASE_AUTH}/register",
        json={
            "username": "validuser",
            "email": long_email,
            "password": "secret123",
        },
    )
    # 255 passa (max_length=255). Vamos com 256:
    too_long = ("a" * 251) + "@b.com"
    response = await client.post(
        f"{BASE_AUTH}/register",
        json={
            "username": "validuser2",
            "email": too_long,
            "password": "secret123",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_nome_alimento_muito_longo_rejeita(client: AsyncClient, test_db):
    """Nome de alimento > 255 chars rejeitado."""
    headers = await register_and_login(client, test_db, "user1")
    response = await client.post(
        BASE,
        json={"nome": "a" * 256, "calorias": 100},
        headers=headers,
    )
    assert response.status_code == 422


# ============================================================
# Quantidade absurda
# ============================================================
@pytest.mark.asyncio
async def test_quantidade_zero_rejeita(client: AsyncClient, test_db):
    """Quantidade 0 rejeitada (tem que ser > 0)."""
    admin_h = await register_and_login(client, test_db, "admin", is_admin=True)
    al = await create_approved_alimento(client, admin_h, "Arroz")
    user_h = await register_and_login(client, test_db, "user1")

    response = await client.post(
        "/alimentacao",
        json={
            "alimento_id": al["id"],
            "quantidade": 0,
            "refeicao": "almoco",
            "data": "2026-08-10",
        },
        headers=user_h,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_quantidade_negativa_rejeita(client: AsyncClient, test_db):
    """Quantidade negativa rejeitada."""
    admin_h = await register_and_login(client, test_db, "admin", is_admin=True)
    al = await create_approved_alimento(client, admin_h, "Arroz")
    user_h = await register_and_login(client, test_db, "user1")

    response = await client.post(
        "/alimentacao",
        json={
            "alimento_id": al["id"],
            "quantidade": -100,
            "refeicao": "almoco",
            "data": "2026-08-10",
        },
        headers=user_h,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_refeicao_invalida_rejeita(client: AsyncClient, test_db):
    """Refeição fora do enum rejeitada."""
    admin_h = await register_and_login(client, test_db, "admin", is_admin=True)
    al = await create_approved_alimento(client, admin_h, "Arroz")
    user_h = await register_and_login(client, test_db, "user1")

    response = await client.post(
        "/alimentacao",
        json={
            "alimento_id": al["id"],
            "quantidade": 100,
            "refeicao": "lanche_da_madruga",  # inválido
            "data": "2026-08-10",
        },
        headers=user_h,
    )
    assert response.status_code == 422


# ============================================================
# Não permite acessar alimentacao de outro user
# ============================================================
@pytest.mark.asyncio
async def test_delete_de_outro_user_via_id_aleatorio(client: AsyncClient, test_db):
    """Tentar deletar alimentacao com ID válido de outro user deve dar 404 (não 403)."""
    admin_h = await register_and_login(client, test_db, "admin", is_admin=True)
    al = await create_approved_alimento(client, admin_h, "Arroz")

    user1_h = await register_and_login(client, test_db, "user1")
    user2_h = await register_and_login(client, test_db, "user2")

    # user1 cria um registro
    created = await client.post(
        "/alimentacao",
        json={
            "alimento_id": al["id"],
            "quantidade": 100,
            "refeicao": "almoco",
            "data": "2026-08-10",
        },
        headers=user1_h,
    )
    reg_id = created.json()["id"]

    # user2 não pode listar nem deletar o registro de user1
    response = await client.get("/alimentacao?data=2026-08-10", headers=user2_h)
    assert all(r["id"] != reg_id for r in response.json())

    response = await client.delete(f"/alimentacao/{reg_id}", headers=user2_h)
    assert response.status_code == 404


# ============================================================
# Token não vaza em logs de erro
# ============================================================
@pytest.mark.asyncio
async def test_erro_nao_vaza_token(client: AsyncClient):
    """Mensagens de erro não devem incluir o token."""
    response = await client.get(
        "/auth/me",
        headers={"Authorization": "Bearer super.secret.token"},
    )
    assert response.status_code == 401
    # Detalhe do erro não deve conter o token
    assert "super.secret.token" not in response.json().get("detail", "")
