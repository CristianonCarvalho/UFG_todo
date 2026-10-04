"""Acesso ao banco para tarefas, sem regras de negócio."""

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.task import Task
from app.schemas.task import TaskStatus


class TaskRepository:
    """Lê e grava tarefas no banco por meio de uma sessão do SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        """Cria o repository sobre a sessão da requisição."""
        self._session = session

    def add(self, task: Task) -> Task:
        """Insere a tarefa e devolve a versão gravada."""
        return self._persist(task)

    def update(self, task: Task) -> Task:
        """Grava as alterações da tarefa e devolve a versão gravada."""
        return self._persist(task)

    def get(self, task_id: int) -> Task | None:
        """Busca uma tarefa pelo id; devolve `None` se não existir."""
        return self._session.get(Task, task_id)

    def list_tasks(self, status: TaskStatus | None = None) -> list[Task]:
        """Lista as tarefas por id, filtrando por status quando informado."""
        consulta = select(Task).order_by(Task.id)
        if status is not None:
            consulta = consulta.where(Task.status == status)
        return list(self._session.scalars(consulta))

    def delete(self, task: Task) -> None:
        """Remove a tarefa do banco."""
        try:
            self._session.delete(task)
            self._session.commit()
        except SQLAlchemyError:
            self._session.rollback()
            raise

    def _persist(self, task: Task) -> Task:
        try:
            self._session.add(task)
            self._session.commit()
            self._session.refresh(task)
        except SQLAlchemyError:
            self._session.rollback()
            raise
        return task
