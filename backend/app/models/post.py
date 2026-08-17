"""
Model de Post (post_media).

- tipo='post' para posts normais (story/reel não no MVP)
- url_s3 é TEXT NOT NULL mas aceita string vazia pra posts só de texto
- is_private esconde o post de quem não é follower aceito
- soft delete via deleted_at
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.alimentacao import MealPlan
    from app.models.user import User


class PostTipo:
    POST = "post"
    STORY = "story"
    REEL = "reel"
    ALL = (POST, STORY, REEL)


class PostMedia(Base, TimestampMixin):
    __tablename__ = "post_media"

    id: Mapped[int] = mapped_column(primary_key=True)

    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # TEXT NOT NULL mas string vazia é aceita (post só de texto)
    url_s3: Mapped[str] = mapped_column(Text, nullable=False, default="")
    legenda: Mapped[str | None] = mapped_column(Text, nullable=True)
    tipo: Mapped[str] = mapped_column(
        String(20), default=PostTipo.POST, nullable=False
    )
    is_private: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Opcional: vincula o post a um plano alimentar
    meal_plan_id: Mapped[int | None] = mapped_column(
        ForeignKey("meal_plans.id", ondelete="SET NULL"),
        nullable=True,
    )

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    # Relationships
    user: Mapped["User"] = relationship("User", lazy="joined")
    meal_plan: Mapped["MealPlan | None"] = relationship("MealPlan")

    __table_args__ = (
        CheckConstraint(
            f"tipo IN {PostTipo.ALL!r}".replace("(", "(").replace(")", ")"),
            name="ck_post_media_tipo",
        ),
    )

    def __repr__(self) -> str:
        return f"<PostMedia id={self.id} user={self.usuario_id} tipo={self.tipo}>"
