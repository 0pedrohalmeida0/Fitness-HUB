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

    Raises:
        UserAlreadyExistsError: se username OU email já existir.
    """
    user = User(
        username=data.username,
        email=data.email,
        senha_hash=hash_password(data.password),
    )

    db.add(user)
    try:
        await db.flush()  # força o INSERT pra detectar conflito agora
    except IntegrityError:
        await db.rollback()
        # Descobre qual campo duplicou
        if await user_exists_by(db, "username", data.username):
            raise UserAlreadyExistsError("Username")
        if await user_exists_by(db, "email", data.email):
            raise UserAlreadyExistsError("Email")
        raise UserAlreadyExistsError("Username ou email")

    return user


async def user_exists_by(db: AsyncSession, field: str, value: str) -> bool:
    """Verifica se já existe usuário com aquele username/email."""
    column = getattr(User, field)
    result = await db.execute(select(User.id).where(column == value))
    return result.scalar_one_or_none() is not None


async def authenticate(db: AsyncSession, data: LoginRequest) -> User:
    """
    Autentica o usuário por email OU username + senha.

    Raises:
        InvalidCredentialsError: se as credenciais forem inválidas.

    Mitigações de segurança:
    - Email é comparado case-insensitive
    - Username mantém case (convenção @pedro != @PEDRO)
    - Sempre chama verify_password (mesmo com user inexistente) pra evitar timing attack
    """
    lookup = data.email_or_username.lower()
    stmt = select(User).where(
        or_(
            func.lower(User.email) == lookup,
            User.username == data.email_or_username,
        )
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
