"""
Routers do social: users, follows, posts, feed, likes, comments.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.social import (
    ComentarioCreate,
    ComentarioPublic,
    FollowRequest,
    FollowResponse,
    LikesRanking,
    PostCreate,
    PostList,
    PostPublic,
    UserPublicFull,
    UserUpdateRequest,
)
from app.services import social_service
from app.services.social_service import (
    CannotFollowSelfError,
    ComentarioAccessDeniedError,
    ComentarioNotFoundError,
    FollowAlreadyExistsError,
    FollowNotFoundError,
    PostAccessDeniedError,
    PostNotFoundError,
)

router = APIRouter(tags=["social"])


# ============================================================
# Users
# ============================================================
@router.get(
    "/users/me",
    response_model=UserPublicFull,
    summary="Perfil do usuário logado",
)
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserPublicFull:
    """Retorna o perfil completo do usuário autenticado."""
    posts_count = await social_service.count_user_posts(db, current_user.id)
    followers_count = await social_service.count_followers(db, current_user.id)
    following_count = await social_service.count_following(db, current_user.id)

    return UserPublicFull(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        nome_completo=current_user.nome_completo,
        bio=current_user.bio,
        foto_url_s3=current_user.foto_url_s3,
        is_private=current_user.is_private,
        is_admin=current_user.is_admin,
        created_at=current_user.created_at,
        posts_count=posts_count,
        followers_count=followers_count,
        following_count=following_count,
        is_following=False,
        is_followed_by=False,
        follow_status="none",
    )


@router.patch(
    "/users/me",
    response_model=UserPublicFull,
    summary="Atualizar perfil",
)
async def update_me(
    data: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserPublicFull:
    """Edita campos do próprio perfil."""
    update = data.model_dump(exclude_unset=True)
    for key, value in update.items():
        if key == "nascimento" and value:
            from datetime import date as date_type
            current_user.nascimento = date_type.fromisoformat(value)
        else:
            setattr(current_user, key, value)
    await db.commit()
    await db.refresh(current_user)
    return await get_me(current_user, db)


@router.get(
    "/users/{username}",
    response_model=UserPublicFull,
    summary="Perfil público de um usuário",
)
async def get_user_profile(
    username: str,
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserPublicFull:
    target = await social_service.get_user_by_username(db, username)
    if target is None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")

    viewer_id = current_user.id if current_user else None
    if not await social_service.can_view_user_profile(db, target, viewer_id):
        # Privado e viewer não segue: mostra perfil básico sem contadores
        return UserPublicFull(
            id=target.id,
            username=target.username,
            email="",  # esconde
            nome_completo=target.nome_completo,
            bio=target.bio,
            foto_url_s3=target.foto_url_s3,
            is_private=target.is_private,
            is_admin=False,
            created_at=target.created_at,
            is_following=False,
            is_followed_by=False,
            follow_status=await social_service.get_follow_status(db, viewer_id, target.id) if viewer_id else "none",
        )

    is_following = (
        await social_service.is_accepted_follow(db, viewer_id, target.id)
        if viewer_id
        else False
    )
    is_followed_by = (
        await social_service.is_accepted_follow(db, target.id, viewer_id)
        if viewer_id
        else False
    )
    follow_status = (
        await social_service.get_follow_status(db, viewer_id, target.id)
        if viewer_id
        else "none"
    )

    return UserPublicFull(
        id=target.id,
        username=target.username,
        email=target.email if target.id == viewer_id else "",
        nome_completo=target.nome_completo,
        bio=target.bio,
        foto_url_s3=target.foto_url_s3,
        is_private=target.is_private,
        is_admin=target.is_admin,
        created_at=target.created_at,
        posts_count=await social_service.count_user_posts(db, target.id),
        followers_count=await social_service.count_followers(db, target.id),
        following_count=await social_service.count_following(db, target.id),
        is_following=is_following,
        is_followed_by=is_followed_by,
        follow_status=follow_status,
    )


@router.get(
    "/users/{username}/posts",
    response_model=PostList,
    summary="Posts de um usuário",
)
async def get_user_posts(
    username: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PostList:
    target = await social_service.get_user_by_username(db, username)
    if target is None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    viewer_id = current_user.id if current_user else None
    posts, total = await social_service.list_user_posts(
        db, target.id, viewer_id, page, page_size
    )
    items = [await social_service.build_post_public(db, p, viewer_id) for p in posts]
    return PostList(items=items, total=total, page=page, page_size=page_size)


# ============================================================
# Follows
# ============================================================
@router.post(
    "/follows/{user_id}",
    response_model=FollowResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Seguir um usuário",
)
async def follow(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FollowResponse:
    try:
        f = await social_service.follow_user(db, current_user.id, user_id)
    except CannotFollowSelfError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FollowNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    await db.commit()
    await db.refresh(f)
    return FollowResponse.model_validate(f)


@router.delete(
    "/follows/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deixar de seguir",
)
async def unfollow(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await social_service.unfollow_user(db, current_user.id, user_id)
    except FollowNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    await db.commit()


@router.patch(
    "/follows/{user_id}",
    response_model=FollowResponse,
    summary="Aceitar/Rejeitar pedido de follow (só o seguido)",
)
async def respond_follow(
    user_id: int,
    body: FollowRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FollowResponse:
    if body.action is None:
        raise HTTPException(status_code=400, detail="action é obrigatório (accept/reject/block).")
    # Map "reject" -> trata como delete (já tratado no service)
    action = body.action
    try:
        f = await social_service.update_follow_status(
            db, current_user.id, user_id, action
        )
    except FollowNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    await db.commit()
    await db.refresh(f)
    return FollowResponse.model_validate(f)


@router.get(
    "/follows/{user_id}/followers",
    summary="Lista de seguidores",
)
async def list_followers(
    user_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    viewer_id = current_user.id if current_user else None
    users, total = await social_service.list_followers(
        db, user_id, viewer_id, page, page_size
    )
    return {
        "items": [{"id": u.id, "username": u.username, "foto_url_s3": u.foto_url_s3} for u in users],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get(
    "/follows/{user_id}/following",
    summary="Lista de quem o user segue",
)
async def list_following(
    user_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    viewer_id = current_user.id if current_user else None
    users, total = await social_service.list_following(
        db, user_id, viewer_id, page, page_size
    )
    return {
        "items": [{"id": u.id, "username": u.username, "foto_url_s3": u.foto_url_s3} for u in users],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get(
    "/follows/pending",
    summary="Pedidos de follow pendentes que EU recebi",
)
async def list_pending(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    pending = await social_service.list_pending_requests(db, current_user.id)
    return {
        "items": [
            {
                "id": p.id,
                "follower_id": p.follower_id,
                "follower_username": p.follower.username if p.follower else None,
                "created_at": p.created_at,
            }
            for p in pending
        ],
        "total": len(pending),
    }


# ============================================================
# Posts
# ============================================================
@router.post(
    "/posts",
    response_model=PostPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Criar um post (texto por enquanto)",
)
async def create_post(
    data: PostCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PostPublic:
    post = await social_service.create_post(db, current_user.id, data)
    await db.commit()
    await db.refresh(post)
    return await social_service.build_post_public(db, post, current_user.id)


@router.get(
    "/posts/{post_id}",
    response_model=PostPublic,
    summary="Detalhe de um post",
)
async def get_post(
    post_id: int,
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PostPublic:
    try:
        post = await social_service.get_post_for_viewer(
            db, post_id, current_user.id if current_user else None
        )
    except PostNotFoundError:
        raise HTTPException(status_code=404, detail="Post não encontrado.")
    except PostAccessDeniedError:
        raise HTTPException(status_code=403, detail="Você não pode ver esse post.")
    return await social_service.build_post_public(
        db, post, current_user.id if current_user else None
    )


@router.delete(
    "/posts/{post_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deletar (soft) um post próprio",
)
async def delete_post(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await social_service.delete_post(db, post_id, current_user.id)
    except PostNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PostAccessDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))
    await db.commit()


# ============================================================
# Feed
# ============================================================
@router.get(
    "/feed",
    response_model=PostList,
    summary="Timeline do usuário logado",
)
async def get_feed(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PostList:
    posts, total = await social_service.get_feed(
        db, current_user.id, page, page_size
    )
    items = [await social_service.build_post_public(db, p, current_user.id) for p in posts]
    return PostList(items=items, total=total, page=page, page_size=page_size)


# ============================================================
# Likes
# ============================================================
@router.post(
    "/posts/{post_id}/like",
    status_code=status.HTTP_201_CREATED,
    summary="Adicionar 1 like (multi-likes permitidos)",
)
async def add_like(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        like = await social_service.add_like(db, current_user.id, post_id)
    except PostNotFoundError:
        raise HTTPException(status_code=404, detail="Post não encontrado.")
    except PostAccessDeniedError:
        raise HTTPException(status_code=403, detail="Você não pode curtir esse post.")
    await db.commit()
    return {"like_id": like.id, "post_id": post_id}


@router.delete(
    "/posts/{post_id}/like",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remover 1 like (o mais recente do user)",
)
async def remove_like(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    removed = await social_service.remove_one_like(db, current_user.id, post_id)
    if removed == 0:
        raise HTTPException(status_code=404, detail="Você não curtiu esse post.")
    await db.commit()


@router.get(
    "/posts/{post_id}/likes",
    response_model=LikesRanking,
    summary="Quem curtiu (ranking por count desc)",
)
async def get_likes(
    post_id: int,
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LikesRanking:
    # Verifica permissão pra ver o post
    try:
        await social_service.get_post_for_viewer(
            db, post_id, current_user.id if current_user else None
        )
    except (PostNotFoundError, PostAccessDeniedError):
        raise HTTPException(status_code=404, detail="Post não encontrado.")
    items, total = await social_service.get_likes_ranking(db, post_id)
    return LikesRanking(items=items, total_likes=total)


# ============================================================
# Comments
# ============================================================
@router.post(
    "/posts/{post_id}/comments",
    response_model=ComentarioPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Criar comentário",
)
async def create_comment(
    post_id: int,
    data: ComentarioCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ComentarioPublic:
    try:
        c = await social_service.create_comentario(
            db, current_user.id, post_id, data
        )
    except PostNotFoundError:
        raise HTTPException(status_code=404, detail="Post não encontrado.")
    except PostAccessDeniedError:
        raise HTTPException(status_code=403, detail="Você não pode comentar nesse post.")
    await db.commit()
    await db.refresh(c)
    return ComentarioPublic(
        id=c.id,
        usuario_id=c.usuario_id,
        post_media_id=c.post_media_id,
        conteudo=c.conteudo,
        created_at=c.created_at,
        autor_username=current_user.username,
        autor_nome=current_user.nome_completo,
        autor_foto_url=current_user.foto_url_s3,
    )


@router.get(
    "/posts/{post_id}/comments",
    response_model=list[ComentarioPublic],
    summary="Listar comentários de um post",
)
async def list_comments(
    post_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ComentarioPublic]:
    try:
        items = await social_service.list_comentarios(
            db, post_id, current_user.id if current_user else None, page, page_size
        )
    except PostNotFoundError:
        raise HTTPException(status_code=404, detail="Post não encontrado.")
    except PostAccessDeniedError:
        raise HTTPException(status_code=403, detail="Você não pode ver esses comentários.")
    return [ComentarioPublic(**item) for item in items]


@router.delete(
    "/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deletar (soft) comentário próprio",
)
async def delete_comment(
    comment_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await social_service.delete_comentario(db, comment_id, current_user.id)
    except ComentarioNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ComentarioAccessDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))
    await db.commit()
