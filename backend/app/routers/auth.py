"""
Endpoints de autenticação.

POST /auth/register  → cria conta + retorna tokens
POST /auth/login     → autentica + retorna tokens
POST /auth/refresh   → renova access token
GET  /auth/me        → dados do usuário logado
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user, security
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserPublic,
)
from app.services import user_service
from app.services.user_service import (
    InvalidCredentialsError,
    UserAlreadyExistsError,
)

router = APIRouter(prefix="/auth", tags=["auth"])


# ============================================================
# Helpers
# ============================================================
def _build_token_response(user: User) -> TokenResponse:
    """Gera o par de tokens (access + refresh) pra um usuário."""
    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
    )


# ============================================================
# Endpoints
# ============================================================
@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar nova conta",
)
async def register(
    data: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Cria uma conta nova.

    - **username**: 3-50 chars, letras/números/ponto/underline, único
    - **email**: formato válido, único
    - **password**: mínimo 8 caracteres (será armazenado como hash bcrypt)
    """
    try:
        user = await user_service.create_user(db, data)
    except UserAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )

    await db.commit()
    await db.refresh(user)
    return _build_token_response(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Entrar com email ou usuário",
)
async def login(
    request: Request,
    data: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Autentica o usuário e retorna access + refresh tokens.

    Aceita email OU username no campo `email_or_username`.
    """
    try:
        user = await user_service.authenticate(db, data)
    except InvalidCredentialsError as e:
        # 401 com mensagem genérica (não vaza se o user existe)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )

    return _build_token_response(user)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Renovar access token",
)
async def refresh(
    data: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Recebe um refresh token válido e retorna um novo par de tokens.
    """
    try:
        payload = decode_token(data.refresh_token)
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Refresh token inválido: {e}",
        )

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token não é um refresh token.",
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido.",
        )

    from sqlalchemy import select
    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não encontrado.",
        )

    return _build_token_response(user)


@router.get(
    "/me",
    response_model=UserPublic,
    summary="Dados do usuário logado",
)
async def me(
    current_user: User = Depends(get_current_user),
) -> UserPublic:
    """Retorna os dados do usuário autenticado (útil pra verificar o token)."""
    return UserPublic.model_validate(current_user)


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Sair (limpar token no cliente)",
)
async def logout() -> MessageResponse:
    """
    Logout "stateless".

    Como o token é JWT, não há sessão pra invalidar no servidor.
    O cliente deve descartar os tokens localmente. Em uma versão
    futura com tokens salvos no banco, este endpoint revogaria o
    refresh token.
    """
    return MessageResponse(message="Logout realizado. Limpe os tokens no cliente.")
