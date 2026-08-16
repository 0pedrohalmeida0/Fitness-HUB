"""
Aplicação principal do Fitness Hub.

FastAPI + CORS + Rate Limiting + Routers.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app import __version__
from app.core.config import settings
from app.routers import alimentacao, alimentos, auth, health


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Hook de startup/shutdown."""
    # Startup
    print(f"🚀 {settings.app_name} v{__version__} iniciado em {settings.app_env}")
    yield
    # Shutdown
    print("👋 Encerrando...")


# Cria a aplicação
app = FastAPI(
    title=settings.app_name,
    version=__version__,
    description="Backend do Fitness Hub — rede social fitness com diário alimentar.",
    lifespan=lifespan,
    debug=settings.app_debug,
)

# ----- CORS -----
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----- Rate Limiting -----
# Limiter configurado mas ainda sem decorators aplicados nas rotas.
# Pra ativar: @limiter.limit("5/minute") em endpoints sensíveis (auth).
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ----- Exception handlers -----
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={
            "detail": f"Limite de requisições excedido. Tente novamente em {exc.detail}."
        },
    )


# ----- Routers -----
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(alimentos.router)
app.include_router(alimentacao.router)


# ----- Root -----
@app.get("/", tags=["root"])
async def root():
    return {
        "app": settings.app_name,
        "version": __version__,
        "env": settings.app_env,
        "docs": "/docs",
    }
