"""
Aplicação principal do Fitness Hub.

FastAPI + CORS + Rate Limiting + Routers + Security Headers.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest

from app import __version__
from app.core.config import settings
from app.core.rate_limit import limiter
from app.routers import alimentacao, alimentos, auth, health, social


# ============================================================
# Middleware: Headers de segurança
# ============================================================
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adiciona headers de segurança em TODA resposta."""

    async def dispatch(self, request: StarletteRequest, call_next):
        response = await call_next(request)
        # Previne MIME sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        # Previne clickjacking (não pode ser embeddado em iframe)
        response.headers["X-Frame-Options"] = "DENY"
        # XSS protection legado (browsers modernos ignoram, mas não atrapalha)
        response.headers["X-XSS-Protection"] = "1; mode=block"
        # Referrer policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # Permissões restritas (geolocation, microphone, etc)
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        # HSTS — só em produção (HTTPS)
        if settings.app_env == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        # Content Security Policy — defesa em profundidade contra XSS
        # Frontend é HTML estático servido separado, então 'self' para assets
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "  # inline styles OK (CSS-in-JS não, mas usaremos)
            "img-src 'self' https: data:; "  # data: pra avatares gerados; https pra S3 futuro
            "connect-src 'self' http://localhost:8000 http://127.0.0.1:8000; "  # API
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Hook de startup/shutdown."""
    print(f"🚀 {settings.app_name} v{__version__} iniciado em {settings.app_env}")
    yield
    print("👋 Encerrando...")


# Cria a aplicação
# Em produção, esconde /docs e /redoc
app = FastAPI(
    title=settings.app_name,
    version=__version__,
    description="Backend do Fitness Hub — rede social fitness com diário alimentar.",
    lifespan=lifespan,
    debug=settings.app_debug,
    docs_url="/docs" if settings.app_env != "production" else None,
    redoc_url="/redoc" if settings.app_env != "production" else None,
    openapi_url="/openapi.json" if settings.app_env != "production" else None,
)

# ----- CORS (deve vir ANTES do security headers, por causa do OPTIONS preflight) -----
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],  # explícito (não "*")
    allow_headers=["Authorization", "Content-Type"],
    max_age=600,
)

# ----- Security Headers -----
app.add_middleware(SecurityHeadersMiddleware)

# ----- Rate Limiting -----
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ----- Routers -----
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(alimentos.router)
app.include_router(alimentacao.router)
app.include_router(social.router)


# ----- Root -----
@app.get("/", tags=["root"])
async def root():
    return {
        "app": settings.app_name,
        "version": __version__,
        "env": settings.app_env,
    }
