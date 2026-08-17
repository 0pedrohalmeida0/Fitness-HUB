"""
Lógica de negócio do social: users, follows, posts, likes, comments.

Princípios:
- Toda checagem de privacidade é feita aqui (não confiar no frontend)
- Posts de user privado só aparecem pra seguidores aceitos
- Likes são públicos (qualquer um pode ver QUEM curtiu, mas só followers veem o post)
- Comments respeitam a privacidade do post pai
"""

from datetime import date as date_type
from typing import Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password  # noqa: F401  (placeholder)
from app.models.comment import Comentario
from app.models.follow import Follow, FollowStatus
from app.models.like import Like
from app.models.post import PostMedia
from app.models.user import User
from app.schemas.social import (
    ComentarioCreate,
    LikedUser,
    PostCreate,
    PostPublic,
)


# ============================================================
# Helpers de privacidade
# ============================================================
async def can_view_user_profile(
    db: AsyncSession,
    target_user: User,
    viewer_id: int | None,
) -> bool:
    """User pode ver o perfil de target?"""
    if viewer_id is None:
        return not target_user.is_private
    if target_user.id == viewer_id:
        return True
    if not target_user.is_private:
        return True
    return await is_accepted_follow(db, viewer_id, target_user.id)


async def can_view_post(
    db: AsyncSession,
    post: PostMedia,
    viewer_id: int | None,
) -> bool:
    """User pode ver esse post?"""
    if post.deleted_at is not None:
        return False
    if post.usuario_id == viewer_id:
        return True
    if not post.is_private:
        return True
    if viewer_id is None:
        return False
    return await is_accepted_follow(db, viewer_id, post.usuario_id)


async def is_accepted_follow(
    db: AsyncSession, follower_id: int, followed_id: int
) -> bool:
    """follower segue followed (status=accepted)?"""
    result = await db.execute(
        select(Follow).where(
            Follow.follower_id == follower_id,
            Follow.followed_id == followed_id,
            Follow.status == FollowStatus.ACCEPTED,
        )
    )
    return result.scalar_one_or_none() is not None


async def get_follow_status(
    db: AsyncSession, follower_id: int, followed_id: int
) -> str:
    """Retorna o status do follow, ou 'none'."""
    result = await db.execute(
        select(Follow).where(
            Follow.follower_id == follower_id,
            Follow.followed_id == followed_id,
        )
    )
    f = result.scalar_one_or_none()
    return f.status if f else "none"


# ============================================================
# Users
# ============================================================
async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def count_user_posts(db: AsyncSession, user_id: int) -> int:
    result = await db.execute(
        select(func.count(PostMedia.id)).where(
            PostMedia.usuario_id == user_id,
            PostMedia.deleted_at.is_(None),
        )
    )
    return result.scalar_one() or 0


async def count_followers(db: AsyncSession, user_id: int) -> int:
    result = await db.execute(
        select(func.count(Follow.id)).where(
            Follow.followed_id == user_id,
            Follow.status == FollowStatus.ACCEPTED,
        )
    )
    return result.scalar_one() or 0


async def count_following(db: AsyncSession, user_id: int) -> int:
    result = await db.execute(
        select(func.count(Follow.id)).where(
            Follow.follower_id == user_id,
            Follow.status == FollowStatus.ACCEPTED,
        )
    )
    return result.scalar_one() or 0


# ============================================================
# Follows
# ============================================================
class FollowError(Exception):
    pass


class CannotFollowSelfError(FollowError):
    pass


class FollowNotFoundError(FollowError):
    pass


class FollowAlreadyExistsError(FollowError):
    pass


async def follow_user(
    db: AsyncSession, follower_id: int, followed_id: int
) -> Follow:
    """Segue um user. Se for privado, vai pra pending."""
    if follower_id == followed_id:
        raise CannotFollowSelfError("Você não pode seguir a si mesmo.")

    target = await get_user_by_id(db, followed_id)
    if target is None:
        raise FollowNotFoundError(f"Usuário {followed_id} não encontrado.")

    # Já existe?
    existing = await db.execute(
        select(Follow).where(
            Follow.follower_id == follower_id,
            Follow.followed_id == followed_id,
        )
    )
    f = existing.scalar_one_or_none()
    if f is not None:
        return f  # idempotente

    # Se o alvo é público, vai direto pra accepted
    status = FollowStatus.PENDING if target.is_private else FollowStatus.ACCEPTED
    f = Follow(
        follower_id=follower_id,
        followed_id=followed_id,
        status=status,
    )
    db.add(f)
    try:
        await db.flush()
    except IntegrityError:
        # Race condition: outra request criou o follow entre o SELECT e o INSERT
        # (UNIQUE(follower_id, followed_id) protege). Rollback e busca o existente.
        await db.rollback()
        existing = await db.execute(
            select(Follow).where(
                Follow.follower_id == follower_id,
                Follow.followed_id == followed_id,
            )
        )
        f = existing.scalar_one_or_none()
        if f is None:
            raise  # erro inesperado
    return f


async def unfollow_user(db: AsyncSession, follower_id: int, followed_id: int) -> None:
    stmt = select(Follow).where(
        Follow.follower_id == follower_id,
        Follow.followed_id == followed_id,
    )
    f = (await db.execute(stmt)).scalar_one_or_none()
    if f is None:
        raise FollowNotFoundError("Você não segue esse usuário.")
    await db.delete(f)
    await db.flush()


async def update_follow_status(
    db: AsyncSession, actor_id: int, target_id: int, new_status: str
) -> Follow:
    """Actor (o seguido) aceita/rejeita/bloqueia target (o follower)."""
    # Mapeia action do schema pra status interno
    if new_status == "accept":
        new_status = FollowStatus.ACCEPTED
    elif new_status == "block":
        new_status = FollowStatus.BLOCKED
    elif new_status == "reject":
        # Reject = deleta o follow
        await unfollow_user(db, target_id, actor_id)
        raise FollowNotFoundError("Follow rejeitado/removido.")
    elif new_status not in (FollowStatus.ACCEPTED, FollowStatus.BLOCKED):
        raise ValueError(f"Status inválido: {new_status}")

    stmt = select(Follow).where(
        Follow.follower_id == target_id,
        Follow.followed_id == actor_id,
    )
    f = (await db.execute(stmt)).scalar_one_or_none()
    if f is None:
        raise FollowNotFoundError("Não tem pedido de follow pendente.")

    f.status = new_status
    await db.flush()
    return f


async def list_followers(
    db: AsyncSession, user_id: int, viewer_id: int | None, page: int, page_size: int
) -> tuple[list[User], int]:
    """Lista seguidores aceitos de um user."""
    # Primeiro checa se viewer pode ver o perfil
    target = await get_user_by_id(db, user_id)
    if target is None:
        return [], 0
    if not await can_view_user_profile(db, target, viewer_id):
        return [], 0

    offset = (page - 1) * page_size
    stmt = (
        select(User)
        .join(Follow, Follow.follower_id == User.id)
        .where(
            Follow.followed_id == user_id,
            Follow.status == FollowStatus.ACCEPTED,
        )
        .order_by(Follow.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    items = list((await db.execute(stmt)).scalars().all())

    count_stmt = select(func.count(Follow.id)).where(
        Follow.followed_id == user_id,
        Follow.status == FollowStatus.ACCEPTED,
    )
    total = (await db.execute(count_stmt)).scalar_one()
    return items, total


async def list_following(
    db: AsyncSession, user_id: int, viewer_id: int | None, page: int, page_size: int
) -> tuple[list[User], int]:
    """Lista quem esse user segue."""
    target = await get_user_by_id(db, user_id)
    if target is None:
        return [], 0
    if not await can_view_user_profile(db, target, viewer_id):
        return [], 0

    offset = (page - 1) * page_size
    stmt = (
        select(User)
        .join(Follow, Follow.followed_id == User.id)
        .where(
            Follow.follower_id == user_id,
            Follow.status == FollowStatus.ACCEPTED,
        )
        .order_by(Follow.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    items = list((await db.execute(stmt)).scalars().all())

    count_stmt = select(func.count(Follow.id)).where(
        Follow.follower_id == user_id,
        Follow.status == FollowStatus.ACCEPTED,
    )
    total = (await db.execute(count_stmt)).scalar_one()
    return items, total


async def list_pending_requests(
    db: AsyncSession, user_id: int
) -> list[Follow]:
    """Lista pedidos de follow pendentes que esse user recebeu."""
    stmt = (
        select(Follow)
        .where(
            Follow.followed_id == user_id,
            Follow.status == FollowStatus.PENDING,
        )
        .order_by(Follow.created_at.asc())
    )
    return list((await db.execute(stmt)).scalars().all())


# ============================================================
# Posts
# ============================================================
class PostNotFoundError(Exception):
    pass


class PostAccessDeniedError(Exception):
    pass


async def create_post(db: AsyncSession, user_id: int, data: PostCreate) -> PostMedia:
    post = PostMedia(
        usuario_id=user_id,
        url_s3=data.url_s3,
        legenda=data.legenda,
        tipo="post",
        is_private=data.is_private,
        meal_plan_id=data.meal_plan_id,
    )
    db.add(post)
    await db.flush()
    return post


async def get_post(db: AsyncSession, post_id: int) -> PostMedia | None:
    result = await db.execute(select(PostMedia).where(PostMedia.id == post_id))
    return result.scalar_one_or_none()


async def get_post_for_viewer(
    db: AsyncSession, post_id: int, viewer_id: int | None
) -> PostMedia:
    """Busca post e valida permissão. Levanta 404 ou 403."""
    post = await get_post(db, post_id)
    if post is None or post.deleted_at is not None:
        raise PostNotFoundError("Post não encontrado.")
    if not await can_view_post(db, post, viewer_id):
        raise PostAccessDeniedError("Você não tem permissão pra ver esse post.")
    return post


async def delete_post(db: AsyncSession, post_id: int, user_id: int) -> None:
    """Soft delete — só o dono pode deletar."""
    post = await get_post(db, post_id)
    if post is None or post.deleted_at is not None:
        raise PostNotFoundError("Post não encontrado.")
    if post.usuario_id != user_id:
        raise PostAccessDeniedError("Só o dono pode deletar o post.")
    from datetime import datetime, timezone
    post.deleted_at = datetime.now(timezone.utc)
    await db.flush()


async def list_user_posts(
    db: AsyncSession,
    user_id: int,
    viewer_id: int | None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[PostMedia], int]:
    """Lista posts de um user (respeitando privacidade)."""
    target = await get_user_by_id(db, user_id)
    if target is None:
        return [], 0
    if not await can_view_user_profile(db, target, viewer_id):
        return [], 0

    offset = (page - 1) * page_size
    base_filter = [
        PostMedia.usuario_id == user_id,
        PostMedia.deleted_at.is_(None),
    ]
    # Se viewer não pode ver posts privados, esconde
    if not await can_view_post_private(db, target, viewer_id):
        base_filter.append(PostMedia.is_private.is_(False))

    stmt = (
        select(PostMedia)
        .where(*base_filter)
        .order_by(PostMedia.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    items = list((await db.execute(stmt)).scalars().all())

    count_stmt = select(func.count(PostMedia.id)).where(*base_filter)
    total = (await db.execute(count_stmt)).scalar_one()
    return items, total


async def can_view_post_private(
    db: AsyncSession, target_user: User, viewer_id: int | None
) -> bool:
    """Viewer pode ver posts privados do target?"""
    if viewer_id is None:
        return False
    if target_user.id == viewer_id:
        return True
    if not target_user.is_private:
        return True
    return await is_accepted_follow(db, viewer_id, target_user.id)


async def get_feed(
    db: AsyncSession,
    viewer_id: int,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[PostMedia], int]:
    """Timeline: posts de quem viewer segue (accepted) + próprios.

    Se você segue alguém (accepted), vê TODOS os posts (públicos e privados).
    Se você só pediu follow (pending), vê só os públicos.
    Posts do próprio viewer sempre aparecem.
    """
    # Subquery: IDs de quem viewer segue (accepted) — esses veem posts privados
    followed_accepted_subq = (
        select(Follow.followed_id)
        .where(
            Follow.follower_id == viewer_id,
            Follow.status == FollowStatus.ACCEPTED,
        )
        .scalar_subquery()
    )

    offset = (page - 1) * page_size
    stmt = (
        select(PostMedia)
        .where(
            PostMedia.deleted_at.is_(None),
            or_(
                # Posts do próprio viewer (todos)
                PostMedia.usuario_id == viewer_id,
                # Posts de quem viewer segue (accepted): TODOS (públicos e privados)
                PostMedia.usuario_id.in_(followed_accepted_subq),
            ),
        )
        .order_by(PostMedia.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    items = list((await db.execute(stmt)).scalars().all())

    count_stmt = select(func.count(PostMedia.id)).where(
        PostMedia.deleted_at.is_(None),
        or_(
            PostMedia.usuario_id == viewer_id,
            PostMedia.usuario_id.in_(followed_accepted_subq),
        ),
    )
    total = (await db.execute(count_stmt)).scalar_one()
    return items, total


async def build_post_public(
    db: AsyncSession,
    post: PostMedia,
    viewer_id: int | None,
) -> PostPublic:
    """Constrói PostPublic com dados do autor e contadores.

    Performance: 1 query pra autor (via relationship com selectinload),
    2 queries agregadas (likes_count + comments_count), 1 condicional
    pro user_like_count. Total: ~4 queries por post (não N+1).
    """
    from app.models.user import User as UserModel

    # Autor (já tem selectinload se vier de listagem)
    autor = (await db.execute(select(UserModel).where(UserModel.id == post.usuario_id))).scalar_one()

    # Contadores agregados em 2 queries (evita cartesian product)
    likes_count = (await db.execute(
        select(func.count(Like.id)).where(Like.post_media_id == post.id)
    )).scalar_one() or 0

    comments_count = (await db.execute(
        select(func.count(Comentario.id)).where(
            Comentario.post_media_id == post.id,
            Comentario.deleted_at.is_(None),
        )
    )).scalar_one() or 0

    # user_like_count só se tiver viewer
    user_like_count = 0
    if viewer_id is not None:
        user_like_count = (await db.execute(
            select(func.count(Like.id)).where(
                Like.post_media_id == post.id,
                Like.usuario_id == viewer_id,
            )
        )).scalar_one() or 0

    return PostPublic(
        id=post.id,
        usuario_id=post.usuario_id,
        legenda=post.legenda,
        url_s3=post.url_s3,
        tipo=post.tipo,
        is_private=post.is_private,
        meal_plan_id=post.meal_plan_id,
        created_at=post.created_at,
        updated_at=post.updated_at,
        autor_username=autor.username,
        autor_nome=autor.nome_completo,
        autor_foto_url=autor.foto_url_s3,
        likes_count=likes_count,
        comments_count=comments_count,
        user_like_count=user_like_count,
    )


async def build_posts_public_bulk(
    db: AsyncSession,
    posts: list[PostMedia],
    viewer_id: int | None,
) -> list[PostPublic]:
    """
    Constrói PostPublic pra vários posts de uma vez.

    Resolve o N+1: ao invés de 4 queries por post, faz:
    - 1 query pra autores (batch)
    - 1 query agregada pra likes/comments (GROUP BY post_id)
    - 1 query pra user_like_count (se viewer)
    Total: 3 queries pra N posts.
    """
    from app.models.user import User as UserModel

    if not posts:
        return []

    post_ids = [p.id for p in posts]
    user_ids = list({p.usuario_id for p in posts})

    # 1) Autores — 1 query pra todos
    autores_q = await db.execute(
        select(UserModel).where(UserModel.id.in_(user_ids))
    )
    autores = {a.id: a for a in autores_q.scalars().all()}

    # 2) Likes count + Comments count agregados — 2 queries (uma por contador)
    #    Poderia ser 1 só, mas manter 2 fica mais legível
    likes_q = await db.execute(
        select(Like.post_media_id, func.count(Like.id))
        .where(Like.post_media_id.in_(post_ids))
        .group_by(Like.post_media_id)
    )
    likes_map = dict(likes_q.all())

    comments_q = await db.execute(
        select(Comentario.post_media_id, func.count(Comentario.id))
        .where(
            Comentario.post_media_id.in_(post_ids),
            Comentario.deleted_at.is_(None),
        )
        .group_by(Comentario.post_media_id)
    )
    comments_map = dict(comments_q.all())

    # 3) user_like_count — 1 query (se viewer)
    user_likes_map: dict[int, int] = {}
    if viewer_id is not None:
        user_likes_q = await db.execute(
            select(Like.post_media_id, func.count(Like.id))
            .where(
                Like.post_media_id.in_(post_ids),
                Like.usuario_id == viewer_id,
            )
            .group_by(Like.post_media_id)
        )
        user_likes_map = dict(user_likes_q.all())

    # Monta a resposta
    out = []
    for post in posts:
        autor = autores.get(post.usuario_id)
        out.append(PostPublic(
            id=post.id,
            usuario_id=post.usuario_id,
            legenda=post.legenda,
            url_s3=post.url_s3,
            tipo=post.tipo,
            is_private=post.is_private,
            meal_plan_id=post.meal_plan_id,
            created_at=post.created_at,
            updated_at=post.updated_at,
            autor_username=autor.username if autor else "?",
            autor_nome=autor.nome_completo if autor else None,
            autor_foto_url=autor.foto_url_s3 if autor else None,
            likes_count=likes_map.get(post.id, 0),
            comments_count=comments_map.get(post.id, 0),
            user_like_count=user_likes_map.get(post.id, 0),
        ))
    return out


# ============================================================
# Likes
# ============================================================
async def add_like(db: AsyncSession, user_id: int, post_id: int) -> Like:
    """Adiciona 1 like. Multi-likes permitidos."""
    # Garante que o post existe e viewer pode ver
    post = await get_post_for_viewer(db, post_id, viewer_id=user_id)
    like = Like(usuario_id=user_id, post_media_id=post.id)
    db.add(like)
    await db.flush()
    return like


async def remove_one_like(db: AsyncSession, user_id: int, post_id: int) -> int:
    """Remove 1 like (o mais recente do user). Retorna quantos foram removidos."""
    from sqlalchemy import delete
    # Pega o like mais recente
    stmt = (
        select(Like)
        .where(
            Like.usuario_id == user_id,
            Like.post_media_id == post_id,
        )
        .order_by(Like.created_at.desc())
        .limit(1)
    )
    like = (await db.execute(stmt)).scalar_one_or_none()
    if like is None:
        return 0
    await db.delete(like)
    await db.flush()
    return 1


async def get_likes_ranking(
    db: AsyncSession, post_id: int
) -> tuple[list[LikedUser], int]:
    """Retorna users que curtiram, ordenados por count desc, depois last_like desc."""
    # Garante que o post existe
    post = await get_post(db, post_id)
    if post is None or post.deleted_at is not None:
        return [], 0

    stmt = (
        select(
            Like.usuario_id,
            User.username,
            User.foto_url_s3,
            func.count(Like.id).label("like_count"),
            func.max(Like.created_at).label("last_like_at"),
        )
        .join(User, User.id == Like.usuario_id)
        .where(Like.post_media_id == post_id)
        .group_by(Like.usuario_id, User.username, User.foto_url_s3)
        .order_by(func.count(Like.id).desc(), func.max(Like.created_at).desc())
    )
    rows = (await db.execute(stmt)).all()

    items = [
        LikedUser(
            usuario_id=r.usuario_id,
            username=r.username,
            foto_url_s3=r.foto_url_s3,
            like_count=r.like_count,
            last_like_at=r.last_like_at,
        )
        for r in rows
    ]
    total = sum(item.like_count for item in items)
    return items, total


# ============================================================
# Comments
# ============================================================
class ComentarioNotFoundError(Exception):
    pass


class ComentarioAccessDeniedError(Exception):
    pass


async def create_comentario(
    db: AsyncSession, user_id: int, post_id: int, data: ComentarioCreate
) -> Comentario:
    """Cria comentário (precisa poder ver o post)."""
    post = await get_post_for_viewer(db, post_id, viewer_id=user_id)
    c = Comentario(
        usuario_id=user_id,
        post_media_id=post.id,
        conteudo=data.conteudo,
    )
    db.add(c)
    await db.flush()
    return c


async def list_comentarios(
    db: AsyncSession, post_id: int, viewer_id: int | None, page: int = 1, page_size: int = 50
) -> list[dict]:
    """Lista comentários (não-deletados) de um post. Verifica permissão antes."""
    post = await get_post_for_viewer(db, post_id, viewer_id=viewer_id)

    offset = (page - 1) * page_size
    stmt = (
        select(Comentario, User)
        .join(User, User.id == Comentario.usuario_id)
        .where(
            Comentario.post_media_id == post.id,
            Comentario.deleted_at.is_(None),
        )
        .order_by(Comentario.created_at.asc())
        .offset(offset)
        .limit(page_size)
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "id": c.id,
            "usuario_id": c.usuario_id,
            "post_media_id": c.post_media_id,
            "conteudo": c.conteudo,
            "created_at": c.created_at,
            "autor_username": u.username,
            "autor_nome": u.nome_completo,
            "autor_foto_url": u.foto_url_s3,
        }
        for c, u in rows
    ]


async def delete_comentario(db: AsyncSession, comentario_id: int, user_id: int) -> None:
    """Soft delete — só o dono do comentário pode deletar."""
    stmt = select(Comentario).where(Comentario.id == comentario_id)
    c = (await db.execute(stmt)).scalar_one_or_none()
    if c is None or c.deleted_at is not None:
        raise ComentarioNotFoundError("Comentário não encontrado.")
    if c.usuario_id != user_id:
        raise ComentarioAccessDeniedError("Só o autor pode deletar.")
    from datetime import datetime, timezone
    c.deleted_at = datetime.now(timezone.utc)
    await db.flush()
