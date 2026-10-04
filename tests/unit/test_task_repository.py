import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.task import Task
from app.repositories.task_repository import TaskRepository
from app.schemas.task import PrioritySource, TaskPriority, TaskStatus


def nova(titulo: str = "t", status: TaskStatus = TaskStatus.PENDENTE) -> Task:
    return Task(
        title=titulo,
        status=status,
        priority=TaskPriority.MEDIA,
        priority_source=PrioritySource.JEV,
    )


def test_add_e_get(session: Session) -> None:
    repo = TaskRepository(session)
    salva = repo.add(nova("primeira"))
    assert salva.id == 1
    assert salva.created_at is not None
    assert repo.get(1) is salva


def test_get_inexistente_devolve_none(session: Session) -> None:
    assert TaskRepository(session).get(999) is None


def test_list_tasks_ordena_por_id_e_filtra_por_status(session: Session) -> None:
    repo = TaskRepository(session)
    repo.add(nova("a"))
    repo.add(nova("b", TaskStatus.CONCLUIDA))
    repo.add(nova("c"))
    assert [t.title for t in repo.list_tasks()] == ["a", "b", "c"]
    assert [t.title for t in repo.list_tasks(TaskStatus.PENDENTE)] == ["a", "c"]
    assert [t.title for t in repo.list_tasks(TaskStatus.CONCLUIDA)] == ["b"]


def test_update_persiste_alteracoes(session: Session) -> None:
    repo = TaskRepository(session)
    tarefa = repo.add(nova("antes"))
    tarefa.title = "depois"
    repo.update(tarefa)
    session.expire_all()
    assert repo.get(tarefa.id).title == "depois"  # type: ignore[union-attr]


def test_delete_remove_a_tarefa(session: Session) -> None:
    repo = TaskRepository(session)
    tarefa = repo.add(nova())
    repo.delete(tarefa)
    assert repo.get(tarefa.id) is None


def test_falha_de_banco_faz_rollback_e_a_sessao_continua_utilizavel(
    session: Session,
) -> None:
    repo = TaskRepository(session)
    invalida = Task(title=None, priority=TaskPriority.MEDIA, priority_source=PrioritySource.JEV)
    with pytest.raises(SQLAlchemyError):
        repo.add(invalida)
    valida = repo.add(nova("depois do erro"))
    assert valida.id is not None
    assert [t.title for t in repo.list_tasks()] == ["depois do erro"]
