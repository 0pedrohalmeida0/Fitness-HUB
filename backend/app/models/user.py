"""
Model do Usuário.

Mapeia 1:1 com a tabela `usuarios` do schema v1.1.

Inclui `deleted_at` (soft delete) para compliance com LGPD/GDPR
(direito ao esquecimento) — exclusão lógica preserva integridade
referencial sem perder histórico.
"""

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Credenciais
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    senha_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # Perfil
    nome_completo: Mapped[str | None] = mapped_column(String(100), nullable=True)
    genero: Mapped[str | None] = mapped_column(String(20), nullable=True)
    nascimento: Mapped[date | None] = mapped_column(Date, nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    foto_url_s3: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Flags
    is_private: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Soft delete (LGPD / GDPR — direito ao esquecimento)
    # Quando setado, queries devem filtrar deleted_at IS NULL
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, index=True
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r}>"
