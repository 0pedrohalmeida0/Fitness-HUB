"""
Testes do módulo social: users, follows, posts, feed, likes, comments.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from app.core.database import AsyncSessionLocal
from app.models.user import User

BASE = ""  # rotas têm prefixos diferentes


# ============================================================
# Helpers
# ============================================================
async def register_and_get_token(client: AsyncClient, username: str) -> str:
    """Registra user e retorna access token."""
    reg = await client.post(
        "/auth/register",
        json={
            "username": username,
            "email": f"{username}@test.com",
            "password": "secret123",
        },
    )
    assert reg.status_code == 201
    return reg.json()["access_token"]


async def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def make_admin(username: str) -> None:
    """Promove um user a admin direto no banco."""
    async with AsyncSessionLocal() as session:
        await session.execute(
            update(User).where(User.username == username).values(is_admin=True)
        )
        await session.commit()


# ============================================================
# Users
# ============================================================
@pytest.mark.asyncio
async def test_get_me(client: AsyncClient):
    """GET /users/me retorna dados do usuário logado."""
    token = await register_and_get_token(client, "meuser")
    response = await client.get("/users/me", headers=await auth_header(token))
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "meuser"
    assert data["posts_count"] == 0
    assert data["followers_count"] == 0
    assert data["following_count"] == 0


@pytest.mark.asyncio
async def test_get_user_profile_publico(client: AsyncClient):
    """GET /users/{username} retorna perfil público."""
    await register_and_get_token(client, "alice")
    # Outro user vê o perfil
    token = await register_and_get_token(client, "bob")
    response = await client.get("/users/alice", headers=await auth_header(token))
    assert response.status_code == 200
    assert response.json()["username"] == "alice"
    assert response.json()["email"] == ""  # esconde email de outros


@pytest.mark.asyncio
async def test_patch_me_atualiza_perfil(client: AsyncClient):
    """PATCH /users/me altera bio, is_private, etc."""
    token = await register_and_get_token(client, "editme")
    response = await client.patch(
        "/users/me",
        json={"bio": "Atleta em evolução", "is_private": True, "nome_completo": "Edit Me"},
        headers=await auth_header(token),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["bio"] == "Atleta em evolução"
    assert data["is_private"] is True
    assert data["nome_completo"] == "Edit Me"


# ============================================================
# Follows
# ============================================================
@pytest.mark.asyncio
async def test_seguir_user_publico_vai_direto_accepted(client: AsyncClient):
    """User público: follow vai direto pra accepted (sem precisar aceitar)."""
    await register_and_get_token(client, "public_user")
    token2 = await register_and_get_token(client, "follower1")

    response = await client.post("/follows/1", headers=await auth_header(token2))
    assert response.status_code == 201
    assert response.json()["status"] == "accepted"


@pytest.mark.asyncio
async def test_seguir_user_privado_vai_para_pending(client: AsyncClient):
    """User privado: follow vai pra pending, esperando aceitação."""
    await register_and_get_token(client, "private_user")
    await client.patch(
        "/users/me", json={"is_private": True}, headers=await auth_header(
            (await register_and_get_token(client, "temp"))  # token temporário
        )
    )
    # Refaz o registro de private_user com is_private direto
    # (mais simples: usa o register_and_get_token + patch com token)
    token_private = await register_and_get_token(client, "priv_target")
    await client.patch(
        "/users/me", json={"is_private": True}, headers=await auth_header(token_private)
    )

    token_follower = await register_and_get_token(client, "trying_to_follow")
    response = await client.post(
        "/follows/2", headers=await auth_header(token_follower)  # ID 2 = priv_target
    )
    assert response.status_code == 201
    assert response.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_nao_pode_seguir_a_si_mesmo(client: AsyncClient):
    token = await register_and_get_token(client, "narcissist")
    response = await client.post("/follows/1", headers=await auth_header(token))
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_unfollow_remove_follow(client: AsyncClient):
    await register_and_get_token(client, "target")
    token = await register_and_get_token(client, "follower")
    await client.post("/follows/1", headers=await auth_header(token))

    # Unfollow
    response = await client.delete("/follows/1", headers=await auth_header(token))
    assert response.status_code == 204

    # Tentar unfollow de novo dá 404
    response = await client.delete("/follows/1", headers=await auth_header(token))
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_aceitar_follow_privado(client: AsyncClient, test_db):
    """Privado: follower pede, seguido aceita, vira accepted."""
    # Cria private user
    token_target = await register_and_get_token(client, "private_alice")
    await client.patch(
        "/users/me", json={"is_private": True}, headers=await auth_header(token_target)
    )

    # Follower pede
    token_follower = await register_and_get_token(client, "fan_bob")
    response = await client.post("/follows/1", headers=await auth_header(token_follower))
    assert response.json()["status"] == "pending"

    # Alice aceita
    response = await client.patch(
        "/follows/2",  # ID do fan_bob
        json={"action": "accept"},
        headers=await auth_header(token_target),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"


@pytest.mark.asyncio
async def test_listar_seguidores(client: AsyncClient):
    await register_and_get_token(client, "celebrity")
    fans = ["fan_one", "fan_two", "fan_three"]
    for f in fans:
        await register_and_get_token(client, f)
    for f in fans:
        login = await client.post(
            "/auth/login",
            json={"email_or_username": f, "password": "secret123"},
        )
        token = login.json()["access_token"]
        await client.post("/follows/1", headers=await auth_header(token))

    # Lista seguidores
    response = await client.get(
        "/follows/1/followers",
        headers=await auth_header(
            (await client.post(
                "/auth/login",
                json={"email_or_username": "celebrity", "password": "secret123"},
            )).json()["access_token"]
        ),
    )
    assert response.status_code == 200
    assert response.json()["total"] == 3


# ============================================================
# Posts
# ============================================================
@pytest.mark.asyncio
async def test_criar_post_texto(client: AsyncClient):
    """POST /posts com texto simples."""
    token = await register_and_get_token(client, "author1")
    response = await client.post(
        "/posts",
        json={"legenda": "Meu primeiro post!"},
        headers=await auth_header(token),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["legenda"] == "Meu primeiro post!"
    assert data["url_s3"] == ""  # sem mídia
    assert data["autor_username"] == "author1"
    assert data["likes_count"] == 0
    assert data["comments_count"] == 0


@pytest.mark.asyncio
async def test_post_vazio_rejeita(client: AsyncClient):
    token = await register_and_get_token(client, "author2")
    response = await client.post(
        "/posts",
        json={"legenda": "   "},  # só espaços
        headers=await auth_header(token),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_post_muito_longo_rejeita(client: AsyncClient):
    token = await register_and_get_token(client, "author3")
    response = await client.post(
        "/posts",
        json={"legenda": "a" * 2001},  # > 2000
        headers=await auth_header(token),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_post_com_xss_na_legenda_aceita(client: AsyncClient):
    """Backend aceita (frontend tem que escapar)."""
    token = await register_and_get_token(client, "xssauthor")
    response = await client.post(
        "/posts",
        json={"legenda": "<script>alert(1)</script>"},
        headers=await auth_header(token),
    )
    assert response.status_code == 201
    # Legenda é preservada como string
    assert response.json()["legenda"] == "<script>alert(1)</script>"


@pytest.mark.asyncio
async def test_deletar_post_proprio(client: AsyncClient):
    token = await register_and_get_token(client, "deleter")
    post = (await client.post(
        "/posts", json={"legenda": "vou deletar"}, headers=await auth_header(token)
    )).json()

    response = await client.delete(f"/posts/{post['id']}", headers=await auth_header(token))
    assert response.status_code == 204

    # Tentar ver depois
    response = await client.get(f"/posts/{post['id']}", headers=await auth_header(token))
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_nao_pode_deletar_post_de_outro(client: AsyncClient):
    await register_and_get_token(client, "victim")
    token = await register_and_get_token(client, "attacker")
    post = (await client.post(
        "/posts", json={"legenda": "post do victim"}, headers=await auth_header(
            (await client.post(
                "/auth/login",
                json={"email_or_username": "victim", "password": "secret123"},
            )).json()["access_token"]
        )
    )).json()

    response = await client.delete(f"/posts/{post['id']}", headers=await auth_header(token))
    assert response.status_code == 403


# ============================================================
# Feed
# ============================================================
@pytest.mark.asyncio
async def test_feed_mostra_proprios_e_quem_sigo(client: AsyncClient):
    """Feed tem os posts do próprio user + de quem segue (accepted)."""
    # 3 users: alice (privado), bob (público), carol (sem follow)
    await register_and_get_token(client, "alice")
    token_bob = await register_and_get_token(client, "bob")
    await register_and_get_token(client, "carol")

    # Alice cria post
    token_alice = (await client.post(
        "/auth/login", json={"email_or_username": "alice", "password": "secret123"}
    )).json()["access_token"]
    await client.post(
        "/posts", json={"legenda": "post da alice"}, headers=await auth_header(token_alice)
    )

    # Bob cria post
    await client.post(
        "/posts", json={"legenda": "post do bob"}, headers=await auth_header(token_bob)
    )

    # Carol cria post
    token_carol = (await client.post(
        "/auth/login", json={"email_or_username": "carol", "password": "secret123"}
    )).json()["access_token"]
    await client.post(
        "/posts", json={"legenda": "post da carol"}, headers=await auth_header(token_carol)
    )

    # Bob segue Carol
    await client.post("/follows/3", headers=await auth_header(token_bob))

    # Feed do Bob: tem post do próprio Bob + da Carol (segue), NÃO tem da Alice
    response = await client.get("/feed", headers=await auth_header(token_bob))
    assert response.status_code == 200
    legendas = [p["legenda"] for p in response.json()["items"]]
    assert "post do bob" in legendas
    assert "post da carol" in legendas
    assert "post da alice" not in legendas


@pytest.mark.asyncio
async def test_feed_post_privado_de_seguidor_aparece(client: AsyncClient):
    """User segue user privado, post privado aparece no feed."""
    token_alice = await register_and_get_token(client, "alice_priv")
    await client.patch(
        "/users/me", json={"is_private": True}, headers=await auth_header(token_alice)
    )
    token_bob = await register_and_get_token(client, "bob_follower")

    # Bob segue Alice (vai pra pending)
    await client.post("/follows/1", headers=await auth_header(token_bob))
    # Alice aceita
    await client.patch(
        "/follows/2", json={"action": "accept"}, headers=await auth_header(token_alice)
    )

    # Alice posta algo privado
    await client.post(
        "/posts",
        json={"legenda": "post privado da alice", "is_private": True},
        headers=await auth_header(token_alice),
    )

    # Feed do Bob tem o post privado
    response = await client.get("/feed", headers=await auth_header(token_bob))
    legendas = [p["legenda"] for p in response.json()["items"]]
    assert "post privado da alice" in legendas


# ============================================================
# Likes
# ============================================================
@pytest.mark.asyncio
async def test_like_multiplas_vezes(client: AsyncClient):
    """Diferencial: pode curtir o mesmo post várias vezes."""
    token = await register_and_get_token(client, "liker")
    post = (await client.post(
        "/posts", json={"legenda": "post likável"}, headers=await auth_header(token)
    )).json()

    for i in range(3):
        r = await client.post(
            f"/posts/{post['id']}/like", headers=await auth_header(token)
        )
        assert r.status_code == 201

    # Likes ranking tem o user com count=3
    response = await client.get(f"/posts/{post['id']}/likes", headers=await auth_header(token))
    assert response.status_code == 200
    data = response.json()
    assert data["total_likes"] == 3
    assert data["items"][0]["like_count"] == 3


@pytest.mark.asyncio
async def test_ranking_ordena_por_count(client: AsyncClient):
    """Quem curtiu mais aparece primeiro."""
    # Post do user1
    await register_and_get_token(client, "postauthor")
    post = (await client.post(
        "/posts", json={"legenda": "viral"}, headers=await auth_header(
            (await client.post(
                "/auth/login", json={"email_or_username": "postauthor", "password": "secret123"}
            )).json()["access_token"]
        )
    )).json()

    # user2 curte 5x
    await register_and_get_token(client, "heavy")
    token_heavy = (await client.post(
        "/auth/login", json={"email_or_username": "heavy", "password": "secret123"}
    )).json()["access_token"]
    for _ in range(5):
        await client.post(
            f"/posts/{post['id']}/like", headers=await auth_header(token_heavy)
        )

    # user3 curte 1x
    await register_and_get_token(client, "light")
    token_light = (await client.post(
        "/auth/login", json={"email_or_username": "light", "password": "secret123"}
    )).json()["access_token"]
    await client.post(
        f"/posts/{post['id']}/like", headers=await auth_header(token_light)
    )

    # Ranking
    response = await client.get(f"/posts/{post['id']}/likes", headers=await auth_header(
        (await client.post(
            "/auth/login", json={"email_or_username": "postauthor", "password": "secret123"}
        )).json()["access_token"]
    ))
    items = response.json()["items"]
    assert items[0]["username"] == "heavy"  # mais likes
    assert items[0]["like_count"] == 5
    assert items[1]["username"] == "light"
    assert items[1]["like_count"] == 1


@pytest.mark.asyncio
async def test_unlike_remove_um_like(client: AsyncClient):
    token = await register_and_get_token(client, "unliker")
    post = (await client.post(
        "/posts", json={"legenda": "post"}, headers=await auth_header(token)
    )).json()

    for _ in range(3):
        await client.post(f"/posts/{post['id']}/like", headers=await auth_header(token))

    # Remove 1
    response = await client.delete(
        f"/posts/{post['id']}/like", headers=await auth_header(token)
    )
    assert response.status_code == 204

    # Agora tem 2 likes
    response = await client.get(f"/posts/{post['id']}/likes", headers=await auth_header(token))
    assert response.json()["total_likes"] == 2


# ============================================================
# Comments
# ============================================================
@pytest.mark.asyncio
async def test_criar_comentario(client: AsyncClient):
    token = await register_and_get_token(client, "commenter")
    post = (await client.post(
        "/posts", json={"legenda": "post"}, headers=await auth_header(token)
    )).json()

    response = await client.post(
        f"/posts/{post['id']}/comments",
        json={"conteudo": "Que post massa!"},
        headers=await auth_header(token),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["conteudo"] == "Que post massa!"
    assert data["autor_username"] == "commenter"


@pytest.mark.asyncio
async def test_comentario_vazio_rejeita(client: AsyncClient):
    token = await register_and_get_token(client, "commenter2")
    post = (await client.post(
        "/posts", json={"legenda": "p"}, headers=await auth_header(token)
    )).json()
    response = await client.post(
        f"/posts/{post['id']}/comments",
        json={"conteudo": "   "},  # só espaços
        headers=await auth_header(token),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_listar_comentarios(client: AsyncClient):
    token = await register_and_get_token(client, "commenter3")
    post = (await client.post(
        "/posts", json={"legenda": "p"}, headers=await auth_header(token)
    )).json()
    for txt in ["primeiro", "segundo", "terceiro"]:
        await client.post(
            f"/posts/{post['id']}/comments",
            json={"conteudo": txt},
            headers=await auth_header(token),
        )

    response = await client.get(f"/posts/{post['id']}/comments", headers=await auth_header(token))
    assert response.status_code == 200
    assert len(response.json()) == 3


@pytest.mark.asyncio
async def test_deletar_comentario_proprio(client: AsyncClient):
    await register_and_get_token(client, "victim")
    token_other = await register_and_get_token(client, "deleter")
    post = (await client.post(
        "/posts", json={"legenda": "p"}, headers=await auth_header(
            (await client.post(
                "/auth/login",
                json={"email_or_username": "victim", "password": "secret123"},
            )).json()["access_token"]
        )
    )).json()
    comment = (await client.post(
        f"/posts/{post['id']}/comments",
        json={"conteudo": "vou deletar"},
        headers=await auth_header(token_other),
    )).json()

    # Outro user não pode deletar
    response = await client.delete(
        f"/comments/{comment['id']}",
        headers=await auth_header(
            (await client.post(
                "/auth/login",
                json={"email_or_username": "victim", "password": "secret123"},
            )).json()["access_token"]
        ),
    )
    assert response.status_code == 403

    # Próprio user pode
    response = await client.delete(
        f"/comments/{comment['id']}", headers=await auth_header(token_other)
    )
    assert response.status_code == 204


# ============================================================
# Privacidade
# ============================================================
@pytest.mark.asyncio
async def test_post_privado_de_user_privado_nao_aparece_no_feed(client: AsyncClient):
    """User segue user privado, mas post privado só aparece se for aceito."""
    token_alice = await register_and_get_token(client, "secretive")
    await client.patch(
        "/users/me", json={"is_private": True}, headers=await auth_header(token_alice)
    )
    token_bob = await register_and_get_token(client, "aspirant")

    # Bob pede follow (vai pending)
    await client.post("/follows/1", headers=await auth_header(token_bob))
    # Bob NÃO aceitou ainda, mas o follow existe. Alice posta privado.
    await client.post(
        "/posts",
        json={"legenda": "segredo da alice", "is_private": True},
        headers=await auth_header(token_alice),
    )

    # Feed do Bob NÃO tem o post privado (follow pending)
    response = await client.get("/feed", headers=await auth_header(token_bob))
    legendas = [p["legenda"] for p in response.json()["items"]]
    assert "segredo da alice" not in legendas


@pytest.mark.asyncio
async def test_perfil_privado_esconde_posts_para_nao_seguidor(client: AsyncClient):
    """User que não segue conta privada: vê perfil mas sem posts."""
    token_alice = await register_and_get_token(client, "locked")
    await client.patch(
        "/users/me", json={"is_private": True}, headers=await auth_header(token_alice)
    )
    await client.post(
        "/posts", json={"legenda": "post privado"}, headers=await auth_header(token_alice)
    )

    # Outro user vê o perfil mas não vê posts
    token_stranger = await register_and_get_token(client, "stranger")
    response = await client.get("/users/locked/posts", headers=await auth_header(token_stranger))
    assert response.json()["total"] == 0  # sem posts visíveis
