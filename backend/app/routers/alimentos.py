"""
Endpoints do Alimento (catálogo).

GET    /alimentos                 - Lista approved (todos podem ver)
GET    /alimentos/{id}            - Detalhe
POST   /alimentos                 - Criar (vai pra pending, exceto admin)
GET    /alimentos/pending         - Lista pending (só admin)
PATCH  /alimentos/{id}/approve    - Aprovar (só admin)
PATCH  /alimentos/{id}/reject     - Rejeitar (só admin)
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.alimento import (
    AlimentoAdmin,
    AlimentoCreate,
    AlimentoList,
    AlimentoModerate,
    AlimentoPublic,
)
from app.services import alimento_service
from app.services.alimento_service import (
    AlimentoNotFoundError,
    AlimentoPermissionError,
)

router = APIRouter(prefix="/alimentos", tags=["alimentos"])


def _is_admin(user: User) -> bool:
    return bool(user.is_admin)


@router.get(
    "",
    response_model=AlimentoList,
    summary="Lista alimentos aprovados",
)
async def list_alimentos(
    search: str | None = Query(default=None, max_length=100, description="Busca por nome"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> AlimentoList:
    """Lista alimentos do catálogo (status=approved), com busca opcional."""
    items, total = await alimento_service.list_approved(db, search, page, page_size)
    return AlimentoList(
        items=[AlimentoPublic.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/pending",
    response_model=AlimentoList,
    summary="Lista alimentos pendentes (admin only)",
)
async def list_pending_alimentos(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AlimentoList:
    """Lista alimentos aguardando moderação. Apenas admins."""
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Apenas admins podem ver pending.")

    items, total = await alimento_service.list_pending(db, page, page_size)
    return AlimentoList(
        items=[AlimentoAdmin.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{alimento_id}",
    response_model=AlimentoPublic,
    summary="Detalhe de um alimento",
)
async def get_alimento(
    alimento_id: int,
    db: AsyncSession = Depends(get_db),
) -> AlimentoPublic:
    """Retorna o detalhe de um alimento (só mostra se approved, exceto admin)."""
    al = await alimento_service.get_alimento(db, alimento_id)
    if al is None:
        raise HTTPException(status_code=404, detail="Alimento não encontrado.")
    if al.status != "approved":
        raise HTTPException(status_code=404, detail="Alimento não encontrado.")
    return AlimentoPublic.model_validate(al)


@router.post(
    "",
    response_model=AlimentoPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Criar novo alimento",
)
async def create_alimento(
    data: AlimentoCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AlimentoPublic:
    """
    Cria um novo alimento.

    - Se você é admin → vai direto pra `approved`.
    - Se não é admin → vai pra `pending` e aguarda moderação.
    """
    al = await alimento_service.create_alimento(
        db, data, current_user.id, _is_admin(current_user)
    )
    await db.commit()
    await db.refresh(al)
    return AlimentoPublic.model_validate(al)


@router.patch(
    "/{alimento_id}/approve",
    response_model=AlimentoAdmin,
    summary="Aprovar alimento (admin only)",
)
async def approve_alimento(
    alimento_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AlimentoAdmin:
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Apenas admins podem aprovar.")

    try:
        al = await alimento_service.approve_alimento(db, alimento_id, current_user.id)
    except AlimentoNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except AlimentoPermissionError as e:
        raise HTTPException(status_code=409, detail=str(e))

    await db.commit()
    await db.refresh(al)
    return AlimentoAdmin.model_validate(al)


@router.patch(
    "/{alimento_id}/reject",
    response_model=AlimentoAdmin,
    summary="Rejeitar alimento (admin only)",
)
async def reject_alimento(
    alimento_id: int,
    body: AlimentoModerate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AlimentoAdmin:
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Apenas admins podem rejeitar.")

    try:
        al = await alimento_service.reject_alimento(
            db, alimento_id, current_user.id, body.motivo or ""
        )
    except AlimentoNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except AlimentoPermissionError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await db.commit()
    await db.refresh(al)
    return AlimentoAdmin.model_validate(al)
