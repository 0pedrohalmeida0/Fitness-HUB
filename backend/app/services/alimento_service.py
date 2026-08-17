"""
Lógica de negócio do Alimento (catálogo com moderação).
"""

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alimento import Alimento, AlimentoStatus
from app.schemas.alimento import AlimentoCreate


class AlimentoNotFoundError(Exception):
    pass


class AlimentoPermissionError(Exception):
    """User não tem permissão pra essa ação."""
    pass


async def create_alimento(
    db: AsyncSession,
    data: AlimentoCreate,
    created_by_user_id: int,
    is_admin: bool,
) -> Alimento:
    """
    Cria um novo alimento.

    - Se o user é admin → status='approved' direto
    - Se não é admin → status='pending' (vai pra moderação)
    """
    alimento = Alimento(
        nome=data.nome,
        carbo=data.carbo,
        protein=data.protein,
        porcao_base_g=data.porcao_base_g,
        calorias=data.calorias,
        acucares=data.acucares,
        fibras=data.fibras,
        sodio=data.sodio,
        status=AlimentoStatus.APPROVED if is_admin else AlimentoStatus.PENDING,
        created_by=created_by_user_id,
        reviewed_by=created_by_user_id if is_admin else None,
        reviewed_at=func.now() if is_admin else None,
    )
    db.add(alimento)
    await db.flush()
    return alimento


async def list_approved(
    db: AsyncSession,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Alimento], int]:
    """Lista alimentos approved, com busca opcional por nome."""
    stmt = select(Alimento).where(Alimento.status == AlimentoStatus.APPROVED)
    count_stmt = select(func.count(Alimento.id)).where(
        Alimento.status == AlimentoStatus.APPROVED
    )

    if search:
        # Escapa % e _ pra não serem interpretados como wildcards do LIKE
        safe = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        term = f"%{safe.lower()}%"
        stmt = stmt.where(func.lower(Alimento.nome).like(term, escape="\\"))
        count_stmt = count_stmt.where(
            func.lower(Alimento.nome).like(term, escape="\\")
        )

    total = (await db.execute(count_stmt)).scalar_one()
    offset = (page - 1) * page_size
    stmt = stmt.order_by(Alimento.nome.asc()).offset(offset).limit(page_size)
    items = list((await db.execute(stmt)).scalars().all())
    return items, total


async def list_pending(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Alimento], int]:
    """Lista alimentos pendentes de moderação (só admin)."""
    stmt = select(Alimento).where(Alimento.status == AlimentoStatus.PENDING)
    count_stmt = select(func.count(Alimento.id)).where(
        Alimento.status == AlimentoStatus.PENDING
    )
    total = (await db.execute(count_stmt)).scalar_one()
    offset = (page - 1) * page_size
    stmt = stmt.order_by(Alimento.created_at.asc()).offset(offset).limit(page_size)
    items = list((await db.execute(stmt)).scalars().all())
    return items, total


async def get_alimento(db: AsyncSession, alimento_id: int) -> Alimento | None:
    result = await db.execute(select(Alimento).where(Alimento.id == alimento_id))
    return result.scalar_one_or_none()


async def approve_alimento(
    db: AsyncSession,
    alimento_id: int,
    admin_user_id: int,
) -> Alimento:
    """Admin aprova um alimento pendente."""
    alimento = await get_alimento(db, alimento_id)
    if alimento is None:
        raise AlimentoNotFoundError(f"Alimento {alimento_id} não encontrado.")
    if alimento.status != AlimentoStatus.PENDING:
        raise AlimentoPermissionError(
            f"Alimento já está com status '{alimento.status}', não pode aprovar."
        )
    alimento.status = AlimentoStatus.APPROVED
    alimento.reviewed_by = admin_user_id
    alimento.reviewed_at = func.now()
    alimento.rejeitado_motivo = None
    await db.flush()
    return alimento


async def reject_alimento(
    db: AsyncSession,
    alimento_id: int,
    admin_user_id: int,
    motivo: str,
) -> Alimento:
    """Admin rejeita um alimento com motivo."""
    if not motivo or len(motivo.strip()) < 5:
        raise ValueError("Motivo da rejeição é obrigatório (mínimo 5 caracteres).")

    alimento = await get_alimento(db, alimento_id)
    if alimento is None:
        raise AlimentoNotFoundError(f"Alimento {alimento_id} não encontrado.")
    if alimento.status != AlimentoStatus.PENDING:
        raise AlimentoPermissionError(
            f"Alimento já está com status '{alimento.status}', não pode rejeitar."
        )
    alimento.status = AlimentoStatus.REJECTED
    alimento.reviewed_by = admin_user_id
    alimento.reviewed_at = func.now()
    alimento.rejeitado_motivo = motivo.strip()
    await db.flush()
    return alimento
