"""
Endpoints da Alimentação (log diário).

POST   /alimentacao              - Registra um consumo
GET    /alimentacao              - Lista de um dia (?data=YYYY-MM-DD)
GET    /alimentacao/resumo       - Resumo nutricional do dia
DELETE /alimentacao/{id}         - Remove (soft delete)
"""

from datetime import date as date_type

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.alimento import Alimento
from app.models.user import User
from app.schemas.alimentacao import (
    AlimentacaoComAlimento,
    AlimentacaoCreate,
    ResumoDiario,
    _validate_date_range,
)
from app.services import alimentacao_service
from app.services.alimentacao_service import (
    AlimentacaoNotFoundError,
    AlimentoNotApprovedError,
)

router = APIRouter(prefix="/alimentacao", tags=["alimentacao"])


def _parse_data_or_400(data_str: str) -> date_type:
    """Converte YYYY-MM-DD validado, ou levanta 400."""
    try:
        d = date_type.fromisoformat(data_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Data inválida. Use YYYY-MM-DD.")
    try:
        return _validate_date_range(d)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "",
    response_model=AlimentacaoComAlimento,
    status_code=status.HTTP_201_CREATED,
    summary="Registra um consumo no diário",
)
async def create_alimentacao(
    data: AlimentacaoCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AlimentacaoComAlimento:
    """
    Adiciona um registro de consumo ao diário.

    - Só alimentos com status `approved` podem ser usados.
    - Alimentos `pending` ou `rejected` retornam 400 com mensagem clara.
    """
    try:
        reg = await alimentacao_service.create_alimentacao(
            db,
            usuario_id=current_user.id,
            alimento_id=data.alimento_id,
            quantidade=data.quantidade,
            refeicao=data.refeicao,
            data=data.data,
        )
    except AlimentoNotApprovedError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await db.commit()

    # Re-busca com o alimento embutido (mesma transação, lock ainda válido)
    al = (await db.execute(select(Alimento).where(Alimento.id == reg.alimento_id))).scalar_one()

    return AlimentacaoComAlimento(
        id=reg.id,
        usuario_id=reg.usuario_id,
        alimento_id=reg.alimento_id,
        quantidade=reg.quantidade,
        refeicao=reg.refeicao,
        data=reg.data,
        created_at=reg.created_at,
        alimento_nome=al.nome,
        alimento_porcao_base_g=al.porcao_base_g,
        alimento_calorias=al.calorias,
        alimento_carbo=al.carbo,
        alimento_protein=al.protein,
        alimento_fibras=al.fibras,
        alimento_acucares=al.acucares,
        alimento_sodio=al.sodio,
    )


@router.get(
    "",
    response_model=list[AlimentacaoComAlimento],
    summary="Lista registros de um dia",
)
async def list_alimentacao_dia(
    data: str = Query(..., description="Data no formato YYYY-MM-DD"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AlimentacaoComAlimento]:
    """Retorna todos os registros do user pro dia informado."""
    data_parsed = _parse_data_or_400(data)
    return await alimentacao_service.list_alimentacao_dia(
        db, current_user.id, data_parsed
    )


@router.get(
    "/resumo",
    response_model=ResumoDiario,
    summary="Resumo nutricional do dia",
)
async def get_resumo_dia(
    data: str = Query(..., description="Data no formato YYYY-MM-DD"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ResumoDiario:
    """
    Retorna os totais do dia (kcal, macros) e o breakdown por refeição.
    """
    data_parsed = _parse_data_or_400(data)
    return await alimentacao_service.get_resumo_dia(db, current_user.id, data_parsed)


@router.delete(
    "/{alimentacao_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove (soft delete) um registro",
)
async def delete_alimentacao(
    alimentacao_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await alimentacao_service.delete_alimentacao(
            db, current_user.id, alimentacao_id
        )
    except AlimentacaoNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    await db.commit()
