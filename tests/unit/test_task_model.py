from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.task import Task
from app.schemas.task import PrioritySource, TaskPriority, TaskStatus


def test_persiste_com_valores_padrao(session: Session) -> None:
    tarefa = Task(
        title="Escrever relatório",
        priority=TaskPriority.MEDIA,
        priority_source=PrioritySource.JEV,
    )
    session.add(tarefa)
    session.commit()
    session.refresh(tarefa)
    assert tarefa.id == 1
    assert tarefa.status is TaskStatus.PENDENTE
    assert tarefa.description is None
    assert tarefa.created_at is not None


def test_enums_sao_gravados_como_texto_em_portugues(session: Session) -> None:
    session.add(
        Task(
            title="t",
            status=TaskStatus.CONCLUIDA,
            priority=TaskPriority.ALTA,
            priority_source=PrioritySource.FALLBACK,
        )
    )
    session.commit()
    linha = session.execute(text("select status, priority, priority_source from tasks")).one()
    assert tuple(linha) == ("concluida", "alta", "fallback")
