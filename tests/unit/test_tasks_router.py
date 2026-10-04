from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.errors import TaskNotFoundError, register_exception_handlers
from app.dependencies import get_task_service
from app.models.task import Task
from app.routers.tasks import router
from app.schemas.task import (
    PRIORITY_FALLBACK_NOTICE,
    PrioritySource,
    TaskCreate,
    TaskPriority,
    TaskStatus,
    TaskUpdate,
)


def tarefa(
    id: int = 1,
    source: PrioritySource = PrioritySource.JEV,
    status: TaskStatus = TaskStatus.PENDENTE,
) -> Task:
    return Task(
        id=id,
        title="t",
        description=None,
        status=status,
        priority=TaskPriority.MEDIA,
        priority_source=source,
        created_at=datetime(2026, 10, 4),
    )


class FakeService:
    def __init__(self) -> None:
        self.source = PrioritySource.JEV
        self.missing = False
        self.listed_with: list[TaskStatus | None] = []
        self.deleted: list[int] = []

    def _task(self, task_id: int = 1) -> Task:
        if self.missing:
            raise TaskNotFoundError()
        return tarefa(task_id, self.source)

    def create(self, data: TaskCreate) -> Task:
        return tarefa(source=self.source)

    def get(self, task_id: int) -> Task:
        return self._task(task_id)

    def list_tasks(self, status: TaskStatus | None = None) -> list[Task]:
        self.listed_with.append(status)
        return [tarefa(1), tarefa(2)]

    def update(self, task_id: int, data: TaskUpdate) -> Task:
        return self._task(task_id)

    def complete(self, task_id: int) -> Task:
        return self._task(task_id)

    def delete(self, task_id: int) -> None:
        self._task(task_id)
        self.deleted.append(task_id)


@pytest.fixture
def service() -> FakeService:
    return FakeService()


@pytest.fixture
def client(service: FakeService) -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router)
    app.dependency_overrides[get_task_service] = lambda: service
    return TestClient(app, raise_server_exceptions=False)


def test_post_devolve_201_com_aviso_quando_fallback(
    client: TestClient, service: FakeService
) -> None:
    service.source = PrioritySource.FALLBACK
    resposta = client.post("/tasks", json={"title": "t"})
    assert resposta.status_code == 201
    assert resposta.json()["priority_notice"] == PRIORITY_FALLBACK_NOTICE


def test_post_corpo_invalido_devolve_422_amigavel(client: TestClient) -> None:
    resposta = client.post("/tasks", json={})
    assert resposta.status_code == 422
    assert resposta.json()["erro"]["codigo"] == "DADOS_INVALIDOS"


def test_get_lista_repassa_o_filtro_de_status(client: TestClient, service: FakeService) -> None:
    client.get("/tasks")
    client.get("/tasks", params={"status": "concluida"})
    assert service.listed_with == [None, TaskStatus.CONCLUIDA]


def test_get_com_status_invalido_devolve_422_listando_opcoes(client: TestClient) -> None:
    resposta = client.get("/tasks", params={"status": "Pendente"})
    assert resposta.status_code == 422
    assert "pendente" in resposta.text and "concluida" in resposta.text


def test_get_por_id(client: TestClient) -> None:
    resposta = client.get("/tasks/7")
    assert resposta.status_code == 200
    assert resposta.json()["id"] == 7


def test_patch_e_complete_devolvem_200(client: TestClient) -> None:
    assert client.patch("/tasks/1", json={"priority": "baixa"}).status_code == 200
    assert client.patch("/tasks/1/complete").status_code == 200


def test_delete_devolve_204_sem_corpo(client: TestClient, service: FakeService) -> None:
    resposta = client.delete("/tasks/3")
    assert resposta.status_code == 204
    assert resposta.content == b""
    assert service.deleted == [3]


@pytest.mark.parametrize(
    ("metodo", "url"),
    [
        ("get", "/tasks/1"),
        ("patch", "/tasks/1/complete"),
        ("delete", "/tasks/1"),
    ],
)
def test_tarefa_inexistente_devolve_404_amigavel(
    client: TestClient, service: FakeService, metodo: str, url: str
) -> None:
    service.missing = True
    resposta = getattr(client, metodo)(url)
    assert resposta.status_code == 404
    assert resposta.json()["erro"]["codigo"] == "TAREFA_NAO_ENCONTRADA"


@pytest.mark.parametrize("task_id", ["0", "-1", "abc", "99999999999999999999"])
def test_id_invalido_devolve_422_e_nunca_500(client: TestClient, task_id: str) -> None:
    resposta = client.get(f"/tasks/{task_id}")
    assert resposta.status_code == 422
    assert resposta.json()["erro"]["codigo"] == "DADOS_INVALIDOS"
