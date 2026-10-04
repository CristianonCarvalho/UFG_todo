"""Regras de negócio das tarefas."""

from typing import Protocol

from app.core.errors import TaskNotFoundError
from app.models.task import Task
from app.schemas.task import PrioritySource, TaskCreate, TaskStatus, TaskUpdate
from app.services.priority_classifier import PriorityClassifier


class TaskRepositoryPort(Protocol):
    """Operações de persistência que o service precisa."""

    def add(self, task: Task) -> Task:
        """Insere a tarefa e a devolve gravada."""
        ...

    def get(self, task_id: int) -> Task | None:
        """Busca uma tarefa pelo id."""
        ...

    def list_tasks(self, status: TaskStatus | None = None) -> list[Task]:
        """Lista as tarefas, com filtro opcional de status."""
        ...

    def update(self, task: Task) -> Task:
        """Grava as alterações da tarefa."""
        ...

    def delete(self, task: Task) -> None:
        """Remove a tarefa."""
        ...


class TaskService:
    """Aplica as regras de negócio sobre o repository e o classificador."""

    def __init__(self, repository: TaskRepositoryPort, classifier: PriorityClassifier) -> None:
        """Cria o service com o repository e o classificador de prioridade."""
        self._repository = repository
        self._classifier = classifier

    def create(self, data: TaskCreate) -> Task:
        """Cria a tarefa como pendente, com a prioridade sugerida pelo classificador."""
        resultado = self._classifier.classify(data.title, data.description)
        tarefa = Task(
            title=data.title,
            description=data.description,
            status=TaskStatus.PENDENTE,
            priority=resultado.priority,
            priority_source=resultado.source,
        )
        return self._repository.add(tarefa)

    def get(self, task_id: int) -> Task:
        """Devolve a tarefa ou levanta `TaskNotFoundError`."""
        tarefa = self._repository.get(task_id)
        if tarefa is None:
            raise TaskNotFoundError()
        return tarefa

    def list_tasks(self, status: TaskStatus | None = None) -> list[Task]:
        """Lista as tarefas, filtrando por status quando informado."""
        return self._repository.list_tasks(status)

    def update(self, task_id: int, data: TaskUpdate) -> Task:
        """Aplica só os campos informados; editar a prioridade a marca como manual."""
        tarefa = self.get(task_id)
        if data.title is not None:
            tarefa.title = data.title
        if data.description is not None:
            tarefa.description = data.description
        if data.status is not None:
            tarefa.status = data.status
        if data.priority is not None:
            tarefa.priority = data.priority
            tarefa.priority_source = PrioritySource.MANUAL
        return self._repository.update(tarefa)

    def complete(self, task_id: int) -> Task:
        """Marca a tarefa como concluída; repetir a operação não gera erro."""
        tarefa = self.get(task_id)
        tarefa.status = TaskStatus.CONCLUIDA
        return self._repository.update(tarefa)

    def delete(self, task_id: int) -> None:
        """Remove a tarefa ou levanta `TaskNotFoundError`."""
        self._repository.delete(self.get(task_id))
