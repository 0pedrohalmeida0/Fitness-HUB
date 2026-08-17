"""
Segurança: hash de senha e JWT.

Usa PyJWT (mais seguro e ativo) ao invés de python-jose (que tem CVEs
e não é mais mantido).
"""

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from jwt import InvalidTokenError
from passlib.context import CryptContext

from app.core.config import settings


# ----- Hash de senha -----
# Bcrypt tem limite de 72 bytes — silencia os bytes extras.
# Pra evitar isso, pré-hash com SHA-256 (sempre 32 bytes hex = 64 chars),
# garantindo que QUALQUER senha caiba no bcrypt sem truncar.
#
# SHA-256 não é reversível porque a senha já é protegida pelo bcrypt depois.
# O SHA-256 sozinho não é seguro, mas a combinação SHA-256 + bcrypt
# (pré-hash pra caber no limit) é prática padrão em sistemas modernos.
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=settings.bcrypt_rounds,
)


def _prehash(plain_password: str) -> str:
    """Pré-hash SHA-256 em hex, garantindo entrada <= 72 bytes pro bcrypt."""
    return hashlib.sha256(plain_password.encode("utf-8")).hexdigest()


def hash_password(plain_password: str) -> str:
    """Gera hash bcrypt da senha."""
    return pwd_context.hash(_prehash(plain_password))


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verifica se a senha em texto puro bate com o hash."""
    try:
        return pwd_context.verify(_prehash(plain_password), password_hash)
    except Exception:
        return False


# ----- JWT -----
ALLOWED_TOKEN_TYPES = {"access", "refresh"}


def _create_token(
    subject: str | int,
    expires_delta: timedelta,
    token_type: str,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Cria um token JWT.

    Inclui `jti` (UUID único) pra evitar colisão de hash em testes
    rápidos e pra suportar revogação por JTI no futuro.
    """
    if token_type not in ALLOWED_TOKEN_TYPES:
        raise ValueError(f"token_type inválido: {token_type}")
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": now,
        "exp": now + expires_delta,
        "type": token_type,
        "jti": uuid.uuid4().hex,
    }
    if extra_claims:
        payload.update(extra_claims)
    # PyJWT aceita datetime, retorna str
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: int) -> str:
    """Cria access token (curta duração)."""
    return _create_token(
        subject=user_id,
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
        token_type="access",
    )


def create_refresh_token(user_id: int) -> str:
    """Cria refresh token (longa duração)."""
    return _create_token(
        subject=user_id,
        expires_delta=timedelta(days=settings.refresh_token_expire_days),
        token_type="refresh",
    )


def decode_token(token: str, expected_type: str | None = None) -> dict[str, Any]:
    """
    Decodifica e valida um token JWT.

    Args:
        token: o JWT a decodificar
        expected_type: se passado, valida que o claim `type` é este valor

    Raises:
        InvalidTokenError se o token for inválido, expirado ou com tipo errado.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except InvalidTokenError as e:
        raise InvalidTokenError(f"Token inválido: {e}") from e

    if expected_type is not None:
        token_type = payload.get("type")
        if token_type != expected_type:
            raise InvalidTokenError(
                f"Tipo de token inválido (esperado '{expected_type}', recebido '{token_type}')."
            )

    return payload


# Alias pra compatibilidade com código antigo que importava JWTError
JWTError = InvalidTokenError
