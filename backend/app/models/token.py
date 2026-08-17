"""
Model de refresh tokens com rotação e blacklist.

Cada vez que um refresh é usado, ele é marcado como "revoked" e um novo
par é emitido. Se um token revogado for reutilizado, isso é detectado
(reuse attack) e TODOS os tokens do user são revogados.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RefreshToken(Base):
    """
    Tabela de refresh tokens (válidos E revogados).

    - Validação de token: existe em `tokens` E não está em `revoked_at`
    - Reuse detection: se um token revoked for apresentado, revoke todos
      os tokens do user (sinaliza que o token vazou)
    """
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)

    # SHA-256 do token (não o token em si, pra DB não vazar tokens válidos)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Quando expira (pra cleanup futuro, não pra validação)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # Quando foi revogado (None = ainda válido)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    # Quando foi usado pra emitir um novo (pra rotation)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Token que substituiu este (pra chain de rotation)
    replaced_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("refresh_tokens.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_refresh_tokens_user_active", "user_id", "revoked_at"),
    )

    def __repr__(self) -> str:
        return f"<RefreshToken id={self.id} user={self.user_id} revoked={self.revoked_at is not None}>"
