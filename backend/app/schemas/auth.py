"""
Schemas de autenticação.

Pydantic v2 com validação rigorosa.
"""

import re

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


# ----- Requests -----
class RegisterRequest(BaseModel):
    """POST /auth/register"""

    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="Nome de usuário único. Letras, números, ponto e underline.",
        examples=["sarah.beats"],
    )
    email: EmailStr = Field(
        ...,
        max_length=255,
        description="Email válido e único.",
        examples=["sarah@beats.com"],
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Senha com no mínimo 8 caracteres.",
        examples=["********"],
    )

    @field_validator("username")
    @classmethod
    def validate_username_format(cls, v: str) -> str:
        """Username: apenas letras, números, ponto e underline."""
        if not re.match(r"^[a-zA-Z0-9_.]+$", v):
            raise ValueError(
                "Username pode conter apenas letras, números, ponto (.) e underline (_)."
            )
        return v


class LoginRequest(BaseModel):
    """POST /auth/login"""

    email_or_username: str = Field(
        ...,
        min_length=3,
        max_length=255,
        description="Email OU username.",
        examples=["sarah@beats.com"],
    )
    password: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Senha do usuário.",
        examples=["********"],
    )


class RefreshRequest(BaseModel):
    """POST /auth/refresh"""

    refresh_token: str = Field(..., description="Refresh token recebido no login.")


class LogoutRequest(BaseModel):
    """POST /auth/logout"""

    refresh_token: str = Field(..., description="Refresh token a ser revogado.")


# ----- Responses -----
class TokenResponse(BaseModel):
    """Resposta padrão de autenticação (login/register/refresh)."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(
        ..., description="Tempo de vida do access token em segundos."
    )


class MessageResponse(BaseModel):
    """Resposta genérica com mensagem."""

    message: str
