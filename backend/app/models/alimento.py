"""
Model do Alimento (catálogo).

Mapeia 1:1 com a tabela `alimentos` do schema v1.1.

Fluxo:
- User comum cria alimento → status='pending'
- Admin cria ou aprova → status='approved'
- Admin rejeita → status='rejected' + rejeitado_motivo
- Apenas alimentos 'approved' podem ser usados em alimentacao/meal_plan_items
  (forçado pelo trigger `check_alimento_approved` no banco).
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Float, ForeignKey, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class AlimentoStatus:
    """Constantes para o status do alimento."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ALL = (PENDING, APPROVED, REJECTED)


class Alimento(Base, TimestampMixin):
    __tablename__ = "alimentos"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Identificação
    nome: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # Valores nutricionais (por porcao_base_g)
    carbo: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    protein: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    porcao_base_g: Mapped[float] = mapped_column(
        Float, nullable=False, default=100, server_default="100"
    )
    calorias: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    acucares: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    fibras: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    sodio: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Moderação
    status: Mapped[str] = mapped_column(
        String(20), default=AlimentoStatus.PENDING, server_default="pending", nullable=False, index=True
    )
    rejeitado_motivo: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Auditoria
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_by: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Relationships
    creator: Mapped["User | None"] = relationship(
        "User", foreign_keys=[created_by], lazy="joined"
    )
    reviewer: Mapped["User | None"] = relationship(
        "User", foreign_keys=[reviewed_by], lazy="joined"
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="ck_alimentos_status",
        ),
        CheckConstraint(
            "porcao_base_g > 0",
            name="ck_alimentos_porcao_base_g_positive",
        ),
    )

    def __repr__(self) -> str:
        return f"<Alimento id={self.id} nome={self.nome!r} status={self.status}>"
