"""
Schemas Pydantic do Alimento (catálogo).
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ----- Requests -----
class AlimentoCreate(BaseModel):
    """POST /alimentos - criar alimento novo.

    Vai pra 'pending' se o user não for admin.
    Vai direto pra 'approved' se for admin.
    """

    nome: str = Field(..., min_length=2, max_length=255, examples=["Frango grelhado"])
    carbo: float = Field(default=0, ge=0, description="g de carbo por porção base")
    protein: float = Field(default=0, ge=0, description="g de proteína por porção base")
    porcao_base_g: float = Field(default=100, gt=0, le=10000, description="g de referência")
    calorias: float = Field(default=0, ge=0, description="kcal por porção base")
    acucares: float = Field(default=0, ge=0, description="g de açúcar por porção base")
    fibras: float = Field(default=0, ge=0, description="g de fibra por porção base")
    sodio: float = Field(default=0, ge=0, description="mg de sódio por porção base")

    @field_validator("nome")
    @classmethod
    def strip_nome(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Nome do alimento muito curto.")
        return v


class AlimentoModerate(BaseModel):
    """PATCH /alimentos/{id}/approve ou /reject - ação de admin."""

    motivo: str | None = Field(
        default=None,
        max_length=500,
        description="Motivo (obrigatório em reject, opcional em approve)",
    )


# ----- Responses -----
class AlimentoPublic(BaseModel):
    """Alimento approved visível pra todos."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    carbo: float
    protein: float
    porcao_base_g: float
    calorias: float
    acucares: float
    fibras: float
    sodio: float
    status: Literal["pending", "approved", "rejected"]
    created_at: datetime | None = None
    reviewed_at: datetime | None = None


class AlimentoAdmin(AlimentoPublic):
    """Alimento com metadados extras (só pra admin)."""

    rejeitado_motivo: str | None = None
    created_by: int | None = None
    reviewed_by: int | None = None


class AlimentoList(BaseModel):
    """Lista paginada de alimentos."""

    items: list[AlimentoPublic]
    total: int
    page: int
    page_size: int
