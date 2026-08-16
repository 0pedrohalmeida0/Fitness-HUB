"""
Lógica de negócio da Alimentação (log diário).
"""

from datetime import date as date_type

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alimentacao import Alimentacao
from app.models.alimento import Alimento, AlimentoStatus
from app.schemas.alimentacao import (
    AlimentacaoComAlimento,
    RefeicaoLiteral,
    ResumoDiario,
    ResumoRefeicao,
)


class AlimentacaoNotFoundError(Exception):
    pass


class AlimentoNotApprovedError(Exception):
    """Tentou usar um alimento que não está approved no log."""


async def create_alimentacao(
    db: AsyncSession,
    usuario_id: int,
    alimento_id: int,
    quantidade: float,
    refeicao: RefeicaoLiteral,
    data: date_type,
) -> Alimentacao:
    """
    Registra um consumo no log diário.

    O trigger `check_alimento_approved` no banco garante que
    só alimentos 'approved' podem entrar aqui. A gente valida
    antes pra dar erro 400 amigável em vez de exception 500.
    """
    # Valida o alimento aqui pra dar erro melhor que o trigger
    result = await db.execute(select(Alimento).where(Alimento.id == alimento_id))
    alimento = result.scalar_one_or_none()

    if alimento is None:
        raise ValueError(f"Alimento {alimento_id} não encontrado.")
    if alimento.status != AlimentoStatus.APPROVED:
        raise AlimentoNotApprovedError(
            f"Alimento '{alimento.nome}' ainda não foi aprovado (status: {alimento.status})."
        )

    reg = Alimentacao(
        usuario_id=usuario_id,
        alimento_id=alimento_id,
        quantidade=quantidade,
        refeicao=refeicao,
        data=data,
    )
    db.add(reg)
    await db.flush()
    return reg


async def list_alimentacao_dia(
    db: AsyncSession,
    usuario_id: int,
    data: date_type,
) -> list[AlimentacaoComAlimento]:
    """Lista todos os registros (não-deletados) de um dia, com dados do alimento."""
    stmt = (
        select(Alimentacao, Alimento)
        .join(Alimento, Alimentacao.alimento_id == Alimento.id)
        .where(
            Alimentacao.usuario_id == usuario_id,
            Alimentacao.data == data,
            Alimentacao.deleted_at.is_(None),
        )
        .order_by(Alimentacao.refeicao.asc(), Alimentacao.created_at.asc())
    )
    rows = (await db.execute(stmt)).all()

    result = []
    for reg, al in rows:
        result.append(
            AlimentacaoComAlimento(
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
        )
    return result


async def delete_alimentacao(
    db: AsyncSession,
    usuario_id: int,
    alimentacao_id: int,
) -> None:
    """Soft delete de um registro (só o dono pode deletar)."""
    stmt = select(Alimentacao).where(
        Alimentacao.id == alimentacao_id,
        Alimentacao.usuario_id == usuario_id,
    )
    reg = (await db.execute(stmt)).scalar_one_or_none()

    if reg is None:
        raise AlimentacaoNotFoundError(
            f"Registro {alimentacao_id} não encontrado ou não pertence ao usuário."
        )

    from datetime import datetime, timezone
    reg.deleted_at = datetime.now(timezone.utc)
    await db.flush()


async def get_resumo_dia(
    db: AsyncSession,
    usuario_id: int,
    data: date_type,
) -> ResumoDiario:
    """Calcula o resumo nutricional do dia."""
    registros = await list_alimentacao_dia(db, usuario_id, data)

    resumo = ResumoDiario(usuario_id=usuario_id, data=data)
    por_refeicao: dict[str, ResumoRefeicao] = {}

    for r in registros:
        # Fator de escala: quanto do alimento foi consumido vs a porção base
        fator = r.quantidade / r.alimento_porcao_base_g if r.alimento_porcao_base_g else 0

        kcal = r.alimento_calorias * fator
        carbo = r.alimento_carbo * fator
        prot = r.alimento_protein * fator
        fib = r.alimento_fibras * fator
        acu = r.alimento_acucares * fator
        sod = r.alimento_sodio * fator

        resumo.total_gramas += r.quantidade
        resumo.total_calorias += kcal
        resumo.total_carbo += carbo
        resumo.total_protein += prot
        resumo.total_fibras += fib
        resumo.total_acucares += acu
        resumo.total_sodio += sod

        if r.refeicao not in por_refeicao:
            por_refeicao[r.refeicao] = ResumoRefeicao()
        sub = por_refeicao[r.refeicao]
        sub.total_gramas += r.quantidade
        sub.total_calorias += kcal
        sub.total_carbo += carbo
        sub.total_protein += prot
        sub.total_fibras += fib

    resumo.por_refeicao = por_refeicao
    return resumo
