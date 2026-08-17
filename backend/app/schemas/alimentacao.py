"""
Schemas Pydantic da Alimentação (log diário).
"""

from datetime import date as date_type, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


# Tipos literais
RefeicaoLiteral = Literal[
    "cafe_manha", "lanche_manha", "almoco", "lanche_tarde", "jantar", "ceia"
]


# Limites para data de consumo: não muito no passado, não no futuro
MAX_PAST_DAYS = 365  # 1 ano
MAX_FUTURE_DAYS = 1  # permite só hoje (evita dados com data errada)


def _validate_date_range(v: date_type) -> date_type:
    """Valida que a data não é absurda (passado distante ou futuro)."""
    today = date_type.today()
    if v > today + timedelta(days=MAX_FUTURE_DAYS):
        raise ValueError(
            f"Data não pode ser mais de {MAX_FUTURE_DAYS} dia(s) no futuro."
        )
    if v < today - timedelta(days=MAX_PAST_DAYS):
        raise ValueError(
            f"Data não pode ser mais de {MAX_PAST_DAYS} dias no passado."
        )
    return v


# ----- Requests -----
class AlimentacaoCreate(BaseModel):
    """POST /alimentacao - registrar consumo."""

    alimento_id: int = Field(..., gt=0)
    quantidade: float = Field(..., gt=0, le=10000, description="Quantidade em gramas")
    refeicao: RefeicaoLiteral
    data: date_type = Field(..., description="Data do consumo (YYYY-MM-DD)")

    @field_validator("data")
    @classmethod
    def _check_date(cls, v: date_type) -> date_type:
        return _validate_date_range(v)


class AlimentacaoUpdate(BaseModel):
    """PATCH /alimentacao/{id} - atualizar registro."""

    quantidade: float | None = Field(default=None, gt=0, le=10000)
    refeicao: RefeicaoLiteral | None = None
    data: date_type | None = None

    @field_validator("data")
    @classmethod
    def _check_date(cls, v: date_type | None) -> date_type | None:
        if v is not None:
            return _validate_date_range(v)
        return v


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
