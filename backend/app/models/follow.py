"""
Model de Follow (relacionamento entre usuários).

- status='pending' quando o alvo é privado
- status='accepted' quando aceito (ou o alvo é público, vai direto)
- status='blocked' quando bloqueado (não usado no MVP)
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class FollowStatus:
    PENDING = "pending"
    ACCEPTED = "accepted"
    BLOCKED = "blocked"
    ALL = (PENDING, ACCEPTED, BLOCKED)


class Follow(Base, TimestampMixin):
    __tablename__ = "follows"

    id: Mapped[int] = mapped_column(primary_key=True)

    follower_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    followed_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(20), default=FollowStatus.ACCEPTED, nullable=False
    )

    # Relationships
    follower: Mapped["User"] = relationship(
        "User", foreign_keys=[follower_id], lazy="joined"
    )
    followed: Mapped["User"] = relationship(
        "User", foreign_keys=[followed_id], lazy="joined"
    )

    __table_args__ = (
        UniqueConstraint("follower_id", "followed_id", name="uq_follows_unique"),
        CheckConstraint(
            f"status IN {FollowStatus.ALL!r}".replace("(", "(").replace(")", ")"),
            name="ck_follows_status",
        ),
        CheckConstraint(
            "follower_id != followed_id",
            name="ck_follows_not_self",
        ),
    )

    def __repr__(self) -> str:
        return f"<Follow {self.follower_id} -> {self.followed_id} ({self.status})>"
