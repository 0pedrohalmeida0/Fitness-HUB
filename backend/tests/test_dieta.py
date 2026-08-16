"""
Testes do módulo Dieta (alimentos + alimentação).
"""

import pytest
from httpx import AsyncClient

BASE_ALIMENTOS = "/alimentos"
BASE_ALIMENTACAO = "/alimentacao"


# ============================================================
# Helpers
# ============================================================
async def register_and_login(
    client: AsyncClient,
    test_db,
    username: str = "user1",
    is_admin: bool = False,
) -> dict:
    """Registra um user, loga, retorna os tokens."""
    payload = {
        "username": username,
        "email": f"{username}@test.com",
        "password": "secret123",
    }
    reg = await client.post("/auth/register", json=payload)
    assert reg.status_code == 201
    tokens = reg.json()

    # Se precisa ser admin, atualiza via a sessão de teste compartilhada
    if is_admin:
        from sqlalchemy import update
        from app.models.user import User
        await test_db.execute(
            update(User).where(User.username == username).values(is_admin=True)
        )
        await test_db.commit()

    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def create_approved_alimento(
    client: AsyncClient, headers: dict, nome: str = "Frango", **kwargs
) -> dict:
    """Cria um alimento já como admin (vai direto pra approved)."""
    payload = {
        "nome": nome,
        "carbo": 0,
        "protein": 31,
        "porcao_base_g": 100,
        "calorias": 165,
        "acucares": 0,
        "fibras": 0,
        "sodio": 74,
        **kwargs,
    }
    response = await client.post(BASE_ALIMENTOS, json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


# ============================================================
# /alimentos
# ============================================================
@pytest.mark.asyncio
async def test_user_cria_alimento_vai_para_pending(client: AsyncClient, test_db):
    """User comum cria → status=pending."""
    headers = await register_and_login(client, test_db, "normaluser")

    response = await client.post(
        BASE_ALIMENTOS,
        json={"nome": "Arroz integral", "calorias": 130, "carbo": 28, "protein": 2.5},
        headers=headers,
    )
    assert response.status_code == 201
    assert response.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_admin_cria_alimento_vai_direto_para_approved(client: AsyncClient, test_db):
    """Admin cria → status=approved."""
    headers = await register_and_login(client, test_db, "admin", is_admin=True)

    response = await client.post(
        BASE_ALIMENTOS,
        json={"nome": "Frango grelhado", "calorias": 165, "protein": 31},
        headers=headers,
    )
    assert response.status_code == 201
    assert response.json()["status"] == "approved"


@pytest.mark.asyncio
async def test_listar_apenas_aprovados(client: AsyncClient, test_db):
    """GET /alimentos só retorna approved."""
    admin_h = await register_and_login(client, test_db, "admin", is_admin=True)
    user_h = await register_and_login(client, test_db, "user")

    # Admin cria 1 (approved), user cria 2 (pending)
    await create_approved_alimento(client, admin_h, "Aprovado 1")
    await create_approved_alimento(client, admin_h, "Aprovado 2")
    await client.post(BASE_ALIMENTOS, json={"nome": "Pending 1"}, headers=user_h)
    await client.post(BASE_ALIMENTOS, json={"nome": "Pending 2"}, headers=user_h)

    response = await client.get(BASE_ALIMENTOS)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    nomes = [i["nome"] for i in data["items"]]
    assert "Aprovado 1" in nomes
    assert "Aprovado 2" in nomes
    assert "Pending 1" not in nomes


@pytest.mark.asyncio
async def test_busca_por_nome(client: AsyncClient, test_db):
    """Search filtra por nome (case-insensitive)."""
    admin_h = await register_and_login(client, test_db, "admin", is_admin=True)
    await create_approved_alimento(client, admin_h, "Frango grelhado")
    await create_approved_alimento(client, admin_h, "Arroz integral")
    await create_approved_alimento(client, admin_h, "Batata doce")

    response = await client.get(f"{BASE_ALIMENTOS}?search=frango")
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["nome"] == "Frango grelhado"


@pytest.mark.asyncio
async def test_admin_lista_pending(client: AsyncClient, test_db):
    """GET /alimentos/pending só funciona pra admin."""
    admin_h = await register_and_login(client, test_db, "admin", is_admin=True)
    user_h = await register_and_login(client, test_db, "user")

    await client.post(BASE_ALIMENTOS, json={"nome": "Pending 1"}, headers=user_h)
    await client.post(BASE_ALIMENTOS, json={"nome": "Pending 2"}, headers=user_h)

    # Admin consegue
    response = await client.get(f"{BASE_ALIMENTOS}/pending", headers=admin_h)
    assert response.status_code == 200
    assert response.json()["total"] == 2

    # User não consegue (403)
    response = await client.get(f"{BASE_ALIMENTOS}/pending", headers=user_h)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_aprova_alimento(client: AsyncClient, test_db):
    """PATCH /alimentos/{id}/approve muda status pra approved."""
    admin_h = await register_and_login(client, test_db, "admin", is_admin=True)
    user_h = await register_and_login(client, test_db, "user")

    created = await client.post(
        BASE_ALIMENTOS, json={"nome": "Whey protein"}, headers=user_h
    )
    al_id = created.json()["id"]
    assert created.json()["status"] == "pending"

    response = await client.patch(f"{BASE_ALIMENTOS}/{al_id}/approve", headers=admin_h)
    assert response.status_code == 200
    assert response.json()["status"] == "approved"

    # Agora aparece na lista pública
    list_response = await client.get(BASE_ALIMENTOS)
    assert any(i["nome"] == "Whey protein" for i in list_response.json()["items"])


@pytest.mark.asyncio
async def test_admin_rejeita_com_motivo(client: AsyncClient, test_db):
    """PATCH /alimentos/{id}/reject com motivo."""
    admin_h = await register_and_login(client, test_db, "admin", is_admin=True)
    user_h = await register_and_login(client, test_db, "user")

    created = await client.post(
        BASE_ALIMENTOS, json={"nome": "Alimento duvidoso"}, headers=user_h
    )
    al_id = created.json()["id"]

    # Sem motivo → 400 (service exige motivo)
    response = await client.patch(
        f"{BASE_ALIMENTOS}/{al_id}/reject", json={}, headers=admin_h
    )
    assert response.status_code == 400

    # Com motivo → 200
    response = await client.patch(
        f"{BASE_ALIMENTOS}/{al_id}/reject",
        json={"motivo": "Informação nutricional inconsistente"},
        headers=admin_h,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "rejected"
    assert data["rejeitado_motivo"] == "Informação nutricional inconsistente"


# ============================================================
# /alimentacao
# ============================================================
@pytest.mark.asyncio
async def test_registrar_consumo(client: AsyncClient, test_db):
    """User cria um registro de consumo."""
    admin_h = await register_and_login(client, test_db, "admin", is_admin=True)
    user_h = await register_and_login(client, test_db, "user")

    al = await create_approved_alimento(client, admin_h, "Frango", calorias=165, protein=31)

    response = await client.post(
        BASE_ALIMENTACAO,
        json={
            "alimento_id": al["id"],
            "quantidade": 150,
            "refeicao": "almoco",
            "data": "2026-08-10",
        },
        headers=user_h,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["quantidade"] == 150
    assert data["alimento_nome"] == "Frango"


@pytest.mark.asyncio
async def test_nao_pode_registrar_alimento_pending(client: AsyncClient, test_db):
    """Não dá pra registrar alimento pending (400)."""
    admin_h = await register_and_login(client, test_db, "admin", is_admin=True)
    user_h = await register_and_login(client, test_db, "user")

    # User cria pending
    created = await client.post(
        BASE_ALIMENTOS, json={"nome": "Em análise"}, headers=user_h
    )
    al_id = created.json()["id"]

    # Tenta usar no log → 400
    response = await client.post(
        BASE_ALIMENTACAO,
        json={
            "alimento_id": al_id,
            "quantidade": 100,
            "refeicao": "almoco",
            "data": "2026-08-10",
        },
        headers=user_h,
    )
    assert response.status_code == 400
    assert "aprovado" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_listar_consumos_do_dia(client: AsyncClient, test_db):
    """GET /alimentacao?data= retorna registros do dia."""
    admin_h = await register_and_login(client, test_db, "admin", is_admin=True)
    user_h = await register_and_login(client, test_db, "user")

    al1 = await create_approved_alimento(client, admin_h, "Arroz")
    al2 = await create_approved_alimento(client, admin_h, "Feijão")

    for al, ref in [(al1, "almoco"), (al2, "almoco"), (al1, "jantar")]:
        await client.post(
            BASE_ALIMENTACAO,
            json={
                "alimento_id": al["id"],
                "quantidade": 100,
                "refeicao": ref,
                "data": "2026-08-10",
            },
            headers=user_h,
        )

    response = await client.get(
        f"{BASE_ALIMENTACAO}?data=2026-08-10", headers=user_h
    )
    assert response.status_code == 200
    assert len(response.json()) == 3


@pytest.mark.asyncio
async def test_resumo_dia_soma_macros_corretamente(client: AsyncClient, test_db):
    """GET /alimentacao/resumo calcula kcal e macros somando as porções."""
    admin_h = await register_and_login(client, test_db, "admin", is_admin=True)
    user_h = await register_and_login(client, test_db, "user")

    # Alimento: 100g = 200 kcal, 20g proteína
    al = await create_approved_alimento(
        client, admin_h, "Frango", calorias=200, protein=20, porcao_base_g=100
    )

    # User come 150g no almoço → 300 kcal, 30g proteína
    await client.post(
        BASE_ALIMENTACAO,
        json={
            "alimento_id": al["id"],
            "quantidade": 150,
            "refeicao": "almoco",
            "data": "2026-08-10",
        },
        headers=user_h,
    )

    response = await client.get(
        f"{BASE_ALIMENTACAO}/resumo?data=2026-08-10", headers=user_h
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_calorias"] == 300  # 200 * 1.5
    assert data["total_protein"] == 30    # 20 * 1.5
    assert data["total_gramas"] == 150
    assert "almoco" in data["por_refeicao"]


@pytest.mark.asyncio
async def test_delete_alimentacao_soft_delete(client: AsyncClient, test_db):
    """DELETE marca deleted_at, registro some da listagem."""
    admin_h = await register_and_login(client, test_db, "admin", is_admin=True)
    user_h = await register_and_login(client, test_db, "user")
    al = await create_approved_alimento(client, admin_h, "Arroz")

    created = await client.post(
        BASE_ALIMENTACAO,
        json={
            "alimento_id": al["id"],
            "quantidade": 100,
            "refeicao": "almoco",
            "data": "2026-08-10",
        },
        headers=user_h,
    )
    reg_id = created.json()["id"]

    # Deleta
    response = await client.delete(f"{BASE_ALIMENTACAO}/{reg_id}", headers=user_h)
    assert response.status_code == 204

    # Listagem do dia não retorna mais
    response = await client.get(
        f"{BASE_ALIMENTACAO}?data=2026-08-10", headers=user_h
    )
    assert len(response.json()) == 0


@pytest.mark.asyncio
async def test_delete_de_outro_user_404(client: AsyncClient, test_db):
    """User não pode deletar registro de outro user (404)."""
    admin_h = await register_and_login(client, test_db, "admin", is_admin=True)
    user1_h = await register_and_login(client, test_db, "user1")
    user2_h = await register_and_login(client, test_db, "user2")
    al = await create_approved_alimento(client, admin_h, "Arroz")

    created = await client.post(
        BASE_ALIMENTACAO,
        json={
            "alimento_id": al["id"],
            "quantidade": 100,
            "refeicao": "almoco",
            "data": "2026-08-10",
        },
        headers=user1_h,
    )
    reg_id = created.json()["id"]

    # user2 tenta deletar
    response = await client.delete(f"{BASE_ALIMENTACAO}/{reg_id}", headers=user2_h)
    assert response.status_code == 404
