"""
Model da Alimentação (log diário).

Mapeia 1:1 com a tabela `alimentacao` do schema v1.1.

O que o user comeu em cada dia. Cada registro é (user, alimento, quantidade, refeição, data).
"""

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.alimento import Alimento


class Refeicao:
    """Constantes para o tipo de refeição."""
    CAFE_MANHA = "cafe_manha"
    LANCHE_MANHA = "lanche_manha"
    ALMOCO = "almoco"
    LANCHE_TARDE = "lanche_tarde"
    JANTAR = "jantar"
    CEIA = "ceia"
    ALL = (CAFE_MANHA, LANCHE_MANHA, ALMOCO, LANCHE_TARDE, JANTAR, CEIA)


class Alimentacao(Base, TimestampMixin):
    __tablename__ = "alimentacao"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Quem comeu
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # O quê e quanto
    alimento_id: Mapped[int] = mapped_column(
        ForeignKey("alimentos.id", ondelete="RESTRICT"),
        nullable=False,
    )
    quantidade: Mapped[float] = mapped_column(Float, nullable=False)

    # Quando
    data: Mapped[date] = mapped_column(Date, nullable=False)
    refeicao: Mapped[str] = mapped_column(String(30), nullable=False, index=True)

    # Soft delete
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", lazy="joined")
    alimento: Mapped["Alimento"] = relationship("Alimento", lazy="joined")

    __table_args__ = (
        CheckConstraint("quantidade > 0", name="ck_alimentacao_quantidade_positive"),
        CheckConstraint(
            f"refeicao IN {Refeicao.ALL!r}".replace("(", "(").replace(")", ")"),
            name="ck_alimentacao_refeicao",
        ),
    )

    def __repr__(self) -> str:
        return f"<Alimentacao user={self.usuario_id} alimento={self.alimento_id} data={self.data}>"
