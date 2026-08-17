"""
Models de MealPlan (stub — implementação completa vem depois).

Por enquanto, só existem pra satisfazer a FK do post_media.meal_plan_id
e do meal_plan_item.alimento_id.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.alimentacao import Alimentacao, Refeicao
    from app.models.user import User


class MealPlan(Base, TimestampMixin):
    __tablename__ = "meal_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    descricao: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Soft delete (consistência com outros models)
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, index=True
    )

    __table_args__ = (
        CheckConstraint("length(nome) >= 1", name="ck_meal_plans_nome_nao_vazio"),
    )

    def __repr__(self) -> str:
        return f"<MealPlan id={self.id} user={self.usuario_id} nome={self.nome!r}>"


class MealPlanItem(Base, TimestampMixin):
    __tablename__ = "meal_plan_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    meal_plan_id: Mapped[int] = mapped_column(
        ForeignKey("meal_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,  # queries "items do plano X" — sem índice, full scan
    )
    alimento_id: Mapped[int] = mapped_column(
        ForeignKey("alimentos.id", ondelete="RESTRICT"),
        nullable=False,
    )
    quantidade: Mapped[float] = mapped_column(Float, nullable=False)
    refeicao: Mapped[str] = mapped_column(String(30), nullable=False)
    horario: Mapped[datetime | None] = mapped_column(nullable=True)
    ordem: Mapped[int] = mapped_column(default=0, nullable=False)

    __table_args__ = (
        CheckConstraint("quantidade > 0", name="ck_meal_plan_items_quantidade_positive"),
    )

    def __repr__(self) -> str:
        return f"<MealPlanItem plan={self.meal_plan_id} alimento={self.alimento_id}>"
