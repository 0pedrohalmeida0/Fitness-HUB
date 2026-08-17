"""
Configuração do banco de dados.

SQLAlchemy 2.0 async + asyncpg + Neon.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    """Base para todos os models."""
    pass


# Engine com pool pequeno (Neon é serverless, conexões são caras)
# SQLite (usado em testes) não aceita esses args — detectamos pelo driver
_is_sqlite = settings.database_url.startswith("sqlite")

_engine_kwargs = {"echo": settings.app_debug}
if not _is_sqlite:
    _engine_kwargs.update(
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,  # verifica conexão antes de usar
        pool_recycle=300,    # recicla conexões a cada 5min
    )

engine = create_async_engine(settings.database_url, **_engine_kwargs)

# Factory de sessões
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency que entrega uma sessão por request.

    IMPORTANTE: NÃO faz commit automático. Cada service/router é
    responsável por chamar `await session.commit()` quando uma
    operação precisa ser persistida. Isso evita o problema de um
    endpoint validar input e retornar 400 DEPOIS de já ter feito
    commit de um side-effect anterior.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
