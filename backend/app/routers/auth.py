"""
Endpoints de autenticação.

POST /auth/register  → cria conta + retorna tokens (JSON + cookies httpOnly)
POST /auth/login     → autentica + retorna tokens (JSON + cookies httpOnly)
POST /auth/refresh   → renova access token (rotation + reuse detection)
POST /auth/logout    → revoga refresh token (blacklist) + limpa cookies
GET  /auth/me        → dados do usuário logado

Os tokens JWT são DUPLAMENTE expostos:
1. No body JSON (pra clients que preferem Authorization header)
2. Em cookies httpOnly + Secure + SameSite=Strict (defesa contra XSS)

O frontend vanilla JS usa cookies (recomendado). APIs externas podem
usar o body JSON. As duas formas são equivalentes — pode-se usar uma
ou outra.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user, security
from app.core.rate_limit import limiter
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)
from app.schemas.user import UserPublic
from app.schemas.social import UserPublicFull as UserPublicWithSecrets
from app.services import token_service, user_service
from app.services.user_service import (
    InvalidCredentialsError,
    UserAlreadyExistsError,
)

router = APIRouter(prefix="/auth", tags=["auth"])


# ============================================================
# Helpers
# ============================================================
def _set_auth_cookies(response: Response, access: str, refresh: str) -> None:
    """Seta os tokens em cookies httpOnly. Defesa contra XSS."""
    is_https = settings.app_env == "production"
    # SameSite=Lax funciona quando front e back estão em origens diferentes
    # (dev). Em prod, se estão no mesmo domínio, considere Strict.
    samesite = "lax"
    # Access: curta duração, path raiz
    response.set_cookie(
        key="fh_access_token",
        value=access,
        httponly=True,
        secure=is_https,
        samesite=samesite,
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )
    # Refresh: longa duração, path restrito (só /auth/refresh e /auth/logout)
    response.set_cookie(
        key="fh_refresh_token",
        value=refresh,
        httponly=True,
        secure=is_https,
        samesite=samesite,
        max_age=settings.refresh_token_expire_days * 86400,
        path="/auth",
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie("fh_access_token", path="/")
    response.delete_cookie("fh_refresh_token", path="/auth")


def _build_token_response(access: str, refresh: str) -> TokenResponse:
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
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
@limiter.limit("5/hour")
async def register(
    response: Response,
    request: Request,
    data: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Cria uma conta nova.

    - **username**: 3-50 chars, letras/números/ponto/underline, único
    - **email**: formato válido, único
    - **password**: mínimo 8 caracteres (será armazenado como hash bcrypt)

    Os tokens são retornados no body E em cookies httpOnly (defesa contra XSS).
    """
    try:
        user = await user_service.create_user(db, data)
    except UserAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )

    access, refresh = await token_service.create_token_pair(db, user)
    await db.commit()
    _set_auth_cookies(response, access, refresh)
    return _build_token_response(access, refresh)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Entrar com email ou usuário",
)
@limiter.limit("5/minute")
async def login(
    response: Response,
    request: Request,
    data: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Autentica o usuário e retorna access + refresh tokens.

    Aceita email OU username no campo `email_or_username`. Os tokens
    são retornados no body E em cookies httpOnly.
    """
    try:
        user = await user_service.authenticate(db, data)
    except InvalidCredentialsError as e:
        # 401 com mensagem genérica (não vaza se o user existe)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )

    access, refresh = await token_service.create_token_pair(db, user)
    await db.commit()
    _set_auth_cookies(response, access, refresh)
    return _build_token_response(access, refresh)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Renovar access token (com rotação)",
)
@limiter.limit("10/minute")
async def refresh(
    response: Response,
    request: Request,
    data: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Recebe um refresh token válido e retorna um novo par de tokens.

    Rotação: cada refresh emite um novo par. O token apresentado é
    marcado como revogado. Se um token revogado for apresentado (reuse
    attack), TODOS os tokens do user são revogados.
    """
    result = await token_service.rotate_refresh_token(db, data.refresh_token)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido ou expirado.",
        )
    access, refresh_tok, _user = result
    await db.commit()
    _set_auth_cookies(response, access, refresh_tok)
    return _build_token_response(access, refresh_tok)


@router.get(
    "/me",
    response_model=UserPublicWithSecrets,
    summary="Dados do usuário logado (com email + is_admin)",
)
async def me(
    current_user: User = Depends(get_current_user),
) -> UserPublicWithSecrets:
    """
    Retorna os dados do usuário autenticado.

    Inclui email e is_admin (dados sensíveis) — só o próprio
    usuário pode ver isso. Para dados públicos de OUTROS
    usuários, use /users/{username} (que retorna UserPublic).
    """
    return UserPublicWithSecrets.model_validate(current_user)


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Sair (revoga refresh token + limpa cookies)",
)
async def logout(
    response: Response,
    data: LogoutRequest,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """
    Revoga o refresh token apresentado (blacklist) e limpa os cookies
    httpOnly. Após o logout, mesmo que alguém tenha o refresh token,
    ele não conseguirá mais emitir novos access tokens.
    """
    revoked = await token_service.revoke_refresh_token(db, data.refresh_token)
    await db.commit()
    _clear_auth_cookies(response)
    if not revoked:
        return MessageResponse(message="Token não estava ativo. Logout idempotente.")
    return MessageResponse(message="Logout realizado. Refresh token revogado.")
