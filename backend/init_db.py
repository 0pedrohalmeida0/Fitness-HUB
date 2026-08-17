"""
Inicializa o schema do banco a partir dos models (sem Alembic).
Útil pra dev e testes. Em produção use Alembic.
"""
import asyncio
import os

from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from app.core.database import Base

# Importa os models pra registrar no metadata
import app.models  # noqa: F401


async def main():
    engine = create_async_engine(settings.database_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print(f"OK: schema criado em {settings.database_url}")


if __name__ == "__main__":
    asyncio.run(main())
