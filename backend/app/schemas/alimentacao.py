"""
Schemas Pydantic da Alimentação (log diário).
"""

from datetime import date as date_type, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# Tipos literais
RefeicaoLiteral = Literal[
    "cafe_manha", "lanche_manha", "almoco", "lanche_tarde", "jantar", "ceia"
]


# ----- Requests -----
class AlimentacaoCreate(BaseModel):
    """POST /alimentacao - registrar consumo."""

    alimento_id: int = Field(..., gt=0)
    quantidade: float = Field(..., gt=0, le=10000, description="Quantidade em gramas")
    refeicao: RefeicaoLiteral
    data: date_type = Field(..., description="Data do consumo (YYYY-MM-DD)")


class AlimentacaoUpdate(BaseModel):
    """PATCH /alimentacao/{id} - atualizar registro."""

    quantidade: float | None = Field(default=None, gt=0, le=10000)
    refeicao: RefeicaoLiteral | None = None
    data: date_type | None = None


# ----- Responses -----
class AlimentacaoPublic(BaseModel):
    """Registro de alimentação com dados do alimento embutidos."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    usuario_id: int
    alimento_id: int
    quantidade: float
    refeicao: RefeicaoLiteral
    data: date_type
    created_at: datetime | None = None


class AlimentacaoComAlimento(AlimentacaoPublic):
    """Alimentacao + dados do alimento (pra UI mostrar macros calculados)."""

    alimento_nome: str
    alimento_porcao_base_g: float
    alimento_calorias: float
    alimento_carbo: float
    alimento_protein: float
    alimento_fibras: float
    alimento_acucares: float
    alimento_sodio: float

    @property
    def kcal_total(self) -> float:
        """Calcula kcal consumidos nessa entrada."""
        return (self.alimento_calorias / self.alimento_porcao_base_g) * self.quantidade


class ResumoDiario(BaseModel):
    """Resumo nutricional de um dia."""

    usuario_id: int
    data: date_type
    total_gramas: float = 0
    total_calorias: float = 0
    total_carbo: float = 0
    total_protein: float = 0
    total_fibras: float = 0
    total_acucares: float = 0
    total_sodio: float = 0
    por_refeicao: dict[str, "ResumoRefeicao"] = {}


class ResumoRefeicao(BaseModel):
    """Subtotal por refeição."""

    total_gramas: float = 0
    total_calorias: float = 0
    total_carbo: float = 0
    total_protein: float = 0
    total_fibras: float = 0


# Resolve forward reference
ResumoDiario.model_rebuild()
