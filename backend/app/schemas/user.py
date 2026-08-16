"""
Schemas de usuário.
"""

from datetime import date

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserUpdate(BaseModel):
    """PATCH /users/me — campos opcionais."""

    nome_completo: str | None = Field(default=None, min_length=1, max_length=100)
    bio: str | None = Field(default=None, max_length=500)
    is_private: bool | None = None
    genero: str | None = Field(default=None, max_length=20)
    nascimento: date | None = None
    foto_url_s3: str | None = Field(default=None, max_length=2048)


class UserPublic(BaseModel):
    """Resposta padrão de dados públicos do usuário."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    nome_completo: str | None = None
    bio: str | None = None
    foto_url_s3: str | None = None
    is_private: bool
    is_admin: bool
