"""
Lógica de negócio do usuário.

Centraliza regras de criação, autenticação e consulta.
"""

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest


class UserAlreadyExistsError(Exception):
    """Email ou username já cadastrado."""

    def __init__(self, field: str):
        self.field = field
        super().__init__(f"{field} já está em uso.")


class InvalidCredentialsError(Exception):
    """Credenciais inválidas."""


async def create_user(db: AsyncSession, data: RegisterRequest) -> User:
    """
    Cria um novo usuário.

    Mitigações de segurança:
    - Email é normalizado pra lowercase antes de salvar (evita
      account takeover via Test@Email.com vs test@email.com)
    - Username mantém case (convenção @pedro != @PEDRO)
    - Detecta duplicatas tanto no flush quanto na checagem explícita

    Raises:
        UserAlreadyExistsError: se username OU email já existir.
    """
    # Normaliza email — defesa contra account takeover
    email_normalized = data.email.lower().strip()
    username_normalized = data.username.strip()

    user = User(
        username=username_normalized,
        email=email_normalized,
        senha_hash=hash_password(data.password),
    )

    db.add(user)
    try:
        await db.flush()  # força o INSERT pra detectar conflito agora
    except IntegrityError:
        await db.rollback()
        # Descobre qual campo duplicou (case-insensitive pra email)
        if await user_exists_by(db, "username", username_normalized):
            raise UserAlreadyExistsError("Username")
        if await user_exists_by_email(db, email_normalized):
            raise UserAlreadyExistsError("Email")
        raise UserAlreadyExistsError("Username ou email")

    return user


async def user_exists_by_email(db: AsyncSession, email: str) -> bool:
    """Verifica se email já existe (case-insensitive)."""
    result = await db.execute(
        select(User.id).where(func.lower(User.email) == email.lower())
    )
    return result.scalar_one_or_none() is not None


async def user_exists_by(db: AsyncSession, field: str, value: str) -> bool:
    """Verifica se já existe usuário com aquele username/email."""
    column = getattr(User, field)
    result = await db.execute(select(User.id).where(column == value))
    return result.scalar_one_or_none() is not None


async def authenticate(db: AsyncSession, data: LoginRequest) -> User:
    """
    Autentica o usuário por email OU username + senha.

    Raises:
        InvalidCredentialsError: se as credenciais forem inválidas OU
        se a conta estiver soft-deletada (mesma mensagem genérica).

    Mitigações de segurança:
    - Email é comparado case-insensitive
    - Username mantém case (convenção @pedro != @PEDRO)
    - Sempre chama verify_password (mesmo com user inexistente) pra evitar timing attack
    - Contas soft-deletadas não logam (mesmo que a senha bata)
    """
    lookup = data.email_or_username.lower()
    stmt = select(User).where(
        or_(
            func.lower(User.email) == lookup,
            User.username == data.email_or_username,
        ),
        User.deleted_at.is_(None),  # LGPD: contas deletadas não logam
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        # Timing attack mitigation: hash dummy pra manter tempo similar
        verify_password(data.password, "$2b$12$" + "x" * 53)
        raise InvalidCredentialsError("Email/usuário ou senha incorretos.")

    if not verify_password(data.password, user.senha_hash):
        raise InvalidCredentialsError("Email/usuário ou senha incorretos.")

    return user


async def soft_delete_user(db: AsyncSession, user: User) -> None:
    """
    Soft delete do user (LGPD/GDPR — direito ao esquecimento).

    - Marca deleted_at = now
    - Revoga TODOS os refresh tokens ativos
    - Mantém os dados no banco pra preservar histórico de posts/comments
    """
    from datetime import datetime

    from app.services import token_service

    user.deleted_at = datetime.utcnow()
    await token_service.revoke_all_user_tokens(db, user.id)
