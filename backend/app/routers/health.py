"""
Endpoints de saúde.

GET /health → liveness (sempre 200 se o app subiu)
GET /ready  → readiness (verifica conexão com o banco)

Importante: /ready NÃO vaza detalhes do erro (host, user, network).
Retorna apenas "ok" / "unavailable". Detalhes ficam só no log.
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db

router = APIRouter(tags=["health"])
log = logging.getLogger(__name__)


@router.get("/health", summary="Liveness check")
async def health() -> dict:
    """Verifica se o processo está vivo."""
    return {"status": "ok"}


@router.get("/ready", summary="Readiness check")
async def ready(db: AsyncSession = Depends(get_db)) -> dict:
    """
    Verifica se o app consegue se conectar ao banco.

    Por segurança, NÃO expõe a mensagem de erro original (pode
    vazar hostname, usuário, etc). Detalhes vão pro log.
    """
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ready", "database": "ok"}
    except Exception as e:
        # Log com detalhes pra debug, mas resposta genérica
        log.error("Readiness check failed: %s", e, exc_info=True)
        return {"status": "not_ready", "database": "unavailable"}
