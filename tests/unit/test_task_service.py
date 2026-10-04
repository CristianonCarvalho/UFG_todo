"""Testes das regras de negócio das tarefas."""

from datetime import datetime

import pytest

from app.core.errors import TaskNotFoundError
from app.models.task import Task
from app.schemas.task import (
    PrioritySource,
    TaskCreate,
    TaskPriority,
    TaskStatus,
    TaskUpdate,
)
from app.services.priority_classifier import PriorityResult
from app.services.task_service import TaskService


class FakeRepository:
    """Repository em memória para testar o service."""

    def __init__(self) -> None:
        """Inicializa o armazenamento e o próximo identificador."""
        self.tasks: dict[int, Task] = {}
        self._next_id = 1

    def add(self, task: Task) -> Task:
        """Adiciona uma tarefa ao armazenamento."""
        task.id = self._next_id
        task.created_at = datetime(2026, 10, 4)
        self.tasks[task.id] = task
        self._next_id += 1
        return task

    def get(self, task_id: int) -> Task | None:
        """Busca uma tarefa pelo identificador."""
        return self.tasks.get(task_id)

    def list_tasks(self, status: TaskStatus | None = None) -> list[Task]:
        """Lista tarefas em ordem de identificador, opcionalmente por status."""
        itens = sorted(self.tasks.values(), key=lambda t: t.id)
        return [t for t in itens if status is None or t.status == status]

    def update(self, task: Task) -> Task:
        """Atualiza uma tarefa armazenada."""
        self.tasks[task.id] = task
        return task

    def delete(self, task: Task) -> None:
        """Remove uma tarefa armazenada."""
        del self.tasks[task.id]


class FakeClassifier:
    """Classificador controlável para testar o service."""

    def __init__(self) -> None:
        """Inicializa uma classificação padrão e o registro de chamadas."""
        self.result = PriorityResult(TaskPriority.ALTA, PrioritySource.JEV)
        self.calls: list[tuple[str, str | None]] = []

    def classify(self, title: str, description: str | None) -> PriorityResult:
        """Registra a solicitação e devolve o resultado configurado."""
        self.calls.append((title, description))
        return self.result


@pytest.fixture
def classifier() -> FakeClassifier:
    """Fornece um classificador falso."""
    return FakeClassifier()


@pytest.fixture
def service(classifier: FakeClassifier) -> TaskService:
    """Fornece um service com dependências em memória."""
    return TaskService(FakeRepository(), classifier)


def test_create_define_status_pendente_e_usa_o_jev(
    service: TaskService, classifier: FakeClassifier
) -> None:
    tarefa = service.create(TaskCreate(title="Escrever relatório", description="rascunho"))
    assert tarefa.status is TaskStatus.PENDENTE
    assert tarefa.priority is TaskPriority.ALTA
    assert tarefa.priority_source is PrioritySource.JEV
    assert classifier.calls == [("Escrever relatório", "rascunho")]


def test_create_com_fallback_grava_a_origem_fallback(
    service: TaskService, classifier: FakeClassifier
) -> None:
    classifier.result = PriorityResult(TaskPriority.MEDIA, PrioritySource.FALLBACK)
    tarefa = service.create(TaskCreate(title="t"))
    assert tarefa.priority is TaskPriority.MEDIA
    assert tarefa.priority_source is PrioritySource.FALLBACK


def test_editar_prioridade_marca_manual_sem_chamar_o_classificador(
    service: TaskService, classifier: FakeClassifier
) -> None:
    tarefa = service.create(TaskCreate(title="t"))
    atualizada = service.update(tarefa.id, TaskUpdate(priority=TaskPriority.BAIXA))
    assert atualizada.priority is TaskPriority.BAIXA
    assert atualizada.priority_source is PrioritySource.MANUAL
    assert len(classifier.calls) == 1


def test_editar_prioridade_para_o_mesmo_valor_ainda_marca_manual(service: TaskService) -> None:
    tarefa = service.create(TaskCreate(title="t"))
    atualizada = service.update(tarefa.id, TaskUpdate(priority=TaskPriority.ALTA))
    assert atualizada.priority_source is PrioritySource.MANUAL


def test_editar_titulo_preserva_prioridade_e_origem_manual(
    service: TaskService, classifier: FakeClassifier
) -> None:
    tarefa = service.create(TaskCreate(title="antes"))
    service.update(tarefa.id, TaskUpdate(priority=TaskPriority.BAIXA))
    atualizada = service.update(tarefa.id, TaskUpdate(title="depois", description="nova"))
    assert atualizada.title == "depois"
    assert atualizada.description == "nova"
    assert atualizada.priority is TaskPriority.BAIXA
    assert atualizada.priority_source is PrioritySource.MANUAL
    assert len(classifier.calls) == 1


def test_editar_titulo_nao_altera_origem_automatica(service: TaskService) -> None:
    tarefa = service.create(TaskCreate(title="antes"))
    atualizada = service.update(tarefa.id, TaskUpdate(title="depois"))
    assert atualizada.priority_source is PrioritySource.JEV


def test_update_pode_alterar_o_status(service: TaskService) -> None:
    tarefa = service.create(TaskCreate(title="t"))
    atualizada = service.update(tarefa.id, TaskUpdate(status=TaskStatus.CONCLUIDA))
    assert atualizada.status is TaskStatus.CONCLUIDA


def test_complete_e_idempotente(service: TaskService) -> None:
    tarefa = service.create(TaskCreate(title="t"))
    primeira = service.complete(tarefa.id)
    segunda = service.complete(tarefa.id)
    assert primeira.status is TaskStatus.CONCLUIDA
    assert segunda.status is TaskStatus.CONCLUIDA


def test_list_tasks_filtra_por_status(service: TaskService) -> None:
    a = service.create(TaskCreate(title="a"))
    service.create(TaskCreate(title="b"))
    service.complete(a.id)
    assert [t.title for t in service.list_tasks()] == ["a", "b"]
    assert [t.title for t in service.list_tasks(TaskStatus.PENDENTE)] == ["b"]
    assert [t.title for t in service.list_tasks(TaskStatus.CONCLUIDA)] == ["a"]


def test_delete_remove_a_tarefa(service: TaskService) -> None:
    tarefa = service.create(TaskCreate(title="t"))
    service.delete(tarefa.id)
    with pytest.raises(TaskNotFoundError):
        service.get(tarefa.id)


@pytest.mark.parametrize("operacao", ["get", "update", "complete", "delete"])
def test_id_inexistente_levanta_tarefa_nao_encontrada(service: TaskService, operacao: str) -> None:
    with pytest.raises(TaskNotFoundError):
        if operacao == "update":
            service.update(999, TaskUpdate(title="x"))
        else:
            getattr(service, operacao)(999)
