"""
Endpoints de saúde.

GET /health → liveness (sempre 200 se o app subiu)
GET /ready  → readiness (verifica conexão com o banco)
"""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness check")
async def health() -> dict:
    """Verifica se o processo está vivo."""
    return {"status": "ok"}


@router.get("/ready", summary="Readiness check")
async def ready(db: AsyncSession = Depends(get_db)) -> dict:
    """Verifica se o app consegue se conectar ao banco."""
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ready", "database": "ok"}
    except Exception as e:
        return {"status": "not_ready", "database": f"error: {e}"}
