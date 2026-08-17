"""
Model de Like (curtida).

Diferencial do app: múltiplas curtidas do mesmo user são permitidas.
Cada chamada em POST /posts/{id}/like = +1 like (com cooldown na API).
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.post import PostMedia
    from app.models.user import User


class Like(Base, TimestampMixin):
    __tablename__ = "likes"

    id: Mapped[int] = mapped_column(primary_key=True)

    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,  # queries "posts curtidos pelo user X" — full table scan sem isso
    )
    post_media_id: Mapped[int] = mapped_column(
        ForeignKey("post_media.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", lazy="joined")
    post: Mapped["PostMedia"] = relationship("PostMedia", lazy="joined")

    def __repr__(self) -> str:
        return f"<Like user={self.usuario_id} post={self.post_media_id}>"
