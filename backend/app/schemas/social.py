"""
Schemas Pydantic do social (users, follows, posts, likes, comments).
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _validate_safe_url(v: str | None) -> str | None:
    """
    Bloqueia URLs com esquemas perigosos (javascript:, data:text/html, vbscript:, file:).
    Aceita http(s) e URLs vazias.
    """
    if v is None or v == "":
        return v
    lowered = v.strip().lower()
    dangerous = (
        "javascript:", "data:text/html", "vbscript:", "file:",
        "data:application", "data:image/svg+xml",
    )
    for d in dangerous:
        if lowered.startswith(d):
            raise ValueError(f"Esquema de URL não permitido: {d}")
    return v


# ============================================================
# Users
# ============================================================
class UserPublicFull(BaseModel):
    """Perfil público (com contadores)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str  # email só visível pro próprio user
    nome_completo: str | None = None
    bio: str | None = None
    foto_url_s3: str | None = None
    is_private: bool
    is_admin: bool
    created_at: datetime | None = None

    # Contadores (preenchidos no service)
    posts_count: int = 0
    followers_count: int = 0
    following_count: int = 0

    # Flags de relacionamento (preenchidos no service)
    is_following: bool = False  # viewer segue esse user?
    is_followed_by: bool = False  # esse user segue o viewer?
    follow_status: Optional[Literal["pending", "accepted", "blocked", "none"]] = "none"


class UserUpdateRequest(BaseModel):
    """PATCH /users/me."""

    nome_completo: str | None = Field(default=None, min_length=1, max_length=100)
    bio: str | None = Field(default=None, max_length=500)
    is_private: bool | None = None
    genero: str | None = Field(default=None, max_length=20)
    nascimento: Optional[str] = None  # ISO date string
    foto_url_s3: str | None = Field(default=None, max_length=2048)

    @field_validator("foto_url_s3")
    @classmethod
    def _safe_url(cls, v: str | None) -> str | None:
        return _validate_safe_url(v)


# ============================================================
# Follows
# ============================================================
class FollowRequest(BaseModel):
    """POST /follows/{user_id}."""

    action: Literal["accept", "reject", "block"] | None = None


class FollowResponse(BaseModel):
    """Resposta de follow (status atual)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    follower_id: int
    followed_id: int
    status: Literal["pending", "accepted", "blocked"]
    created_at: datetime | None = None


# ============================================================
# Posts
# ============================================================
class PostCreate(BaseModel):
    """POST /posts."""

    legenda: str = Field(..., min_length=1, max_length=2000)
    url_s3: str = Field(default="", max_length=2048, description="URL do S3 (vazio pra texto)")
    is_private: bool = False
    meal_plan_id: int | None = None

    @field_validator("legenda")
    @classmethod
    def strip_legenda(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Legenda não pode ser vazia.")
        return v

    @field_validator("url_s3")
    @classmethod
    def _safe_url(cls, v: str) -> str:
        return _validate_safe_url(v) or ""


class PostPublic(BaseModel):
    """Post com dados do autor."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    usuario_id: int
    legenda: str | None = None
    url_s3: str
    tipo: str
    is_private: bool
    meal_plan_id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    # Dados do autor
    autor_username: str
    autor_nome: str | None = None
    autor_foto_url: str | None = None

    # Contadores
    likes_count: int = 0
    comments_count: int = 0
    user_like_count: int = 0  # quantas vezes o viewer curtiu (0, 1, 2...)


class PostList(BaseModel):
    """Lista paginada de posts."""

    items: list[PostPublic]
    total: int
    page: int
    page_size: int


# ============================================================
# Likes
# ============================================================
class LikePublic(BaseModel):
    """Like individual (1 curtida)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    usuario_id: int
    post_media_id: int
    created_at: datetime | None = None


class LikedUser(BaseModel):
    """User que curtiu + quantas vezes."""

    usuario_id: int
    username: str
    foto_url_s3: str | None = None
    like_count: int
    last_like_at: datetime


class LikesRanking(BaseModel):
    """Lista de quem curtiu, ordenada por count desc."""

    items: list[LikedUser]
    total_likes: int


# ============================================================
# Comments
# ============================================================
class ComentarioCreate(BaseModel):
    """POST /posts/{id}/comments."""

    conteudo: str = Field(..., min_length=1, max_length=2000)

    @field_validator("conteudo")
    @classmethod
    def strip_conteudo(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Comentário não pode ser vazio.")
        return v


class ComentarioPublic(BaseModel):
    """Comentário com dados do autor."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    usuario_id: int
    post_media_id: int
    conteudo: str
    created_at: datetime | None = None
    autor_username: str
    autor_nome: str | None = None
    autor_foto_url: str | None = None


# ============================================================
# Genérico
# ============================================================
class MessageResponse(BaseModel):
    """Resposta genérica com mensagem."""

    message: str
