"""
Schemas de usuário.
"""

from datetime import date

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


def _validate_safe_url(v: str | None) -> str | None:
    """
    Bloqueia URLs com esquemas perigosos (javascript:, data:, vbscript:, file:).
    Aceita http(s) e URLs relativas.
    """
    if v is None or v == "":
        return v
    lowered = v.strip().lower()
    # Bloqueia esquemas que executam JS no contexto da página
    dangerous = (
        "javascript:", "data:text/html", "vbscript:", "file:",
        "data:application", "data:image/svg+xml",  # SVG pode ter JS embutido
    )
    for d in dangerous:
        if lowered.startswith(d):
            raise ValueError(f"Esquema de URL não permitido: {d}")
    return v


class UserUpdate(BaseModel):
    """PATCH /users/me — campos opcionais."""

    nome_completo: str | None = Field(default=None, min_length=1, max_length=100)
    bio: str | None = Field(default=None, max_length=500)
    is_private: bool | None = None
    genero: str | None = Field(default=None, max_length=20)
    nascimento: date | None = None
    foto_url_s3: str | None = Field(default=None, max_length=2048)

    @field_validator("foto_url_s3")
    @classmethod
    def _safe_url(cls, v: str | None) -> str | None:
        return _validate_safe_url(v)


class UserPublic(BaseModel):
    """Resposta padrão de dados públicos do usuário."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    nome_completo: str | None = None
    bio: str | None = None
    foto_url_s3: str | None = None
    is_private: bool
    # is_admin FOI REMOVIDO do schema público por segurança (enumeração de alvos)
    # Apenas o próprio usuário vê is_admin via /users/me (UserPublicFull no social.py)
