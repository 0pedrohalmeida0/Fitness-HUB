"""
Service de refresh tokens com rotação e detecção de reuso.

Fluxo:
1. Login/Register: cria RefreshToken novo (válido)
2. Refresh:
   a. Apresenta um refresh_token
   b. Verifica: hash existe, não revoked, não usado (ou user_id bate)
   c. Marca como `used_at` + `revoked_at` (rotation: 1 uso = 1 novo)
   d. Cria novo RefreshToken
   e. Retorna novo par (access + refresh)
3. Logout: revoga o token apresentado (marca revoked_at)
4. Reuse detection: se um token revoked for apresentado, revoga todos do user
"""

import hashlib
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.models.token import RefreshToken
from app.models.user import User


def _hash_token(token: str) -> str:
    """SHA-256 do token. Não armazenamos o token em si (DB breach não vaza)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _decode_user_id(token: str) -> int | None:
    """Decodifica o JWT e extrai o user_id (sub). Retorna None se inválido."""
    try:
        payload = decode_token(token, expected_type="refresh")
    except Exception:
        return None
    sub = payload.get("sub")
    if sub is None:
        return None
    try:
        return int(sub)
    except (TypeError, ValueError):
        return None


async def create_token_pair(
    db: AsyncSession, user: User
) -> tuple[str, str]:
    """
    Cria um novo par de tokens (access + refresh) E persiste o refresh
    no banco (válido até expires_at).

    Returns: (access_token, refresh_token)
    """
    access = create_access_token(user.id)
    refresh = create_refresh_token(user.id)

    # Persiste o refresh
    expires_at = datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days)
    db.add(RefreshToken(
        token_hash=_hash_token(refresh),
        user_id=user.id,
        expires_at=expires_at,
    ))
    await db.flush()
    return access, refresh


async def rotate_refresh_token(
    db: AsyncSession, presented_token: str
) -> tuple[str, str, User] | None:
    """
    Rotaciona um refresh token:
    - Valida (existe, não revoked, JWT ok)
    - Detecta reuso (se revoked → revoga TUDO do user)
    - Marca o apresentado como used+revoked
    - Cria novo par
    - Retorna (novo_access, novo_refresh, user) ou None se inválido
    """
    user_id = _decode_user_id(presented_token)
    if user_id is None:
        return None

    token_hash = _hash_token(presented_token)
    stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    record = (await db.execute(stmt)).scalar_one_or_none()
    if record is None:
        return None

    if record.user_id != user_id:
        return None

    if record.revoked_at is not None:
        # REUSE DETECTION: token já foi usado. Revoga todos os tokens do user
        # (sinaliza que o token vazou).
        now = datetime.utcnow()
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == record.user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        return None

    # Carrega o user
    user = (await db.execute(select(User).where(User.id == record.user_id))).scalar_one_or_none()
    if user is None:
        return None

    # Marca o token atual como usado/revoked
    now = datetime.utcnow()
    record.used_at = now
    record.revoked_at = now

    # Cria o novo par
    new_access, new_refresh = await create_token_pair(db, user)

    # Linka o novo ao anterior
    new_record = (await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == _hash_token(new_refresh))
    )).scalar_one()
    record.replaced_by_id = new_record.id

    return new_access, new_refresh, user


async def revoke_refresh_token(db: AsyncSession, presented_token: str) -> bool:
    """
    Revoga um refresh token (logout). Retorna True se revogou, False se não existia.
    """
    token_hash = _hash_token(presented_token)
    record = (await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )).scalar_one_or_none()
    if record is None or record.revoked_at is not None:
        return False
    record.revoked_at = datetime.utcnow()
    await db.flush()
    return True


async def revoke_all_user_tokens(db: AsyncSession, user_id: int) -> int:
    """Revoga todos os tokens válidos do user. Retorna quantos foram revogados."""
    result = await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.utcnow())
    )
    return result.rowcount
