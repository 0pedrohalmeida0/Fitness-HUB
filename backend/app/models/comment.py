"""
Model de Comentário.

- Apenas texto por enquanto (sem imagem/anexo)
- Soft delete via deleted_at
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.post import PostMedia
    from app.models.user import User


class Comentario(Base, TimestampMixin):
    __tablename__ = "comentarios"

    id: Mapped[int] = mapped_column(primary_key=True)

    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False,
    )
    post_media_id: Mapped[int] = mapped_column(
        ForeignKey("post_media.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conteudo: Mapped[str] = mapped_column(Text, nullable=False)

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    # Relationships
    user: Mapped["User"] = relationship("User", lazy="joined")
    post: Mapped["PostMedia"] = relationship("PostMedia")

    __table_args__ = (
        CheckConstraint("length(conteudo) > 0", name="ck_comentarios_nao_vazio"),
        CheckConstraint("length(conteudo) <= 2000", name="ck_comentarios_limite"),
    )

    def __repr__(self) -> str:
        return f"<Comentario user={self.usuario_id} post={self.post_media_id}>"
