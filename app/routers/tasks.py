"""Controller das tarefas: valida a entrada, delega ao service e devolve o código HTTP."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response

from app.core.errors import ErrorResponse
from app.dependencies import get_task_service
from app.models.task import Task
from app.schemas.task import TaskCreate, TaskOut, TaskStatus, TaskUpdate
from app.services.task_service import TaskService

router = APIRouter(prefix="/tasks", tags=["Tarefas"])

ServiceDep = Annotated[TaskService, Depends(get_task_service)]
TaskId = Annotated[
    int,
    Path(ge=1, le=9223372036854775807, description="Identificador da tarefa."),
]

RESPOSTA_422 = {"model": ErrorResponse, "description": "Dados inválidos."}
RESPOSTA_404 = {"model": ErrorResponse, "description": "Tarefa não encontrada."}


@router.post(
    "",
    response_model=TaskOut,
    status_code=201,
    summary="Criar tarefa",
    description="Cria uma tarefa pendente; a prioridade é sugerida automaticamente.",
    responses={422: RESPOSTA_422},
)
def criar_tarefa(data: TaskCreate, service: ServiceDep) -> Task:
    """Cria uma tarefa."""
    return service.create(data)


@router.get(
    "",
    response_model=list[TaskOut],
    summary="Listar tarefas",
    description="Lista as tarefas por id, com filtro opcional por status.",
    responses={422: RESPOSTA_422},
)
def listar_tarefas(
    service: ServiceDep,
    status: Annotated[TaskStatus | None, Query(description="Filtra por status.")] = None,
) -> list[Task]:
    """Lista as tarefas."""
    return service.list_tasks(status)


@router.get(
    "/{task_id}",
    response_model=TaskOut,
    summary="Detalhar tarefa",
    responses={404: RESPOSTA_404, 422: RESPOSTA_422},
)
def detalhar_tarefa(task_id: TaskId, service: ServiceDep) -> Task:
    """Devolve uma tarefa pelo id."""
    return service.get(task_id)


@router.patch(
    "/{task_id}/complete",
    response_model=TaskOut,
    summary="Concluir tarefa",
    description="Marca a tarefa como concluída; repetir a operação não gera erro.",
    responses={404: RESPOSTA_404, 422: RESPOSTA_422},
)
def concluir_tarefa(task_id: TaskId, service: ServiceDep) -> Task:
    """Marca a tarefa como concluída."""
    return service.complete(task_id)


@router.patch(
    "/{task_id}",
    response_model=TaskOut,
    summary="Editar tarefa",
    description="Atualiza os campos informados; editar a prioridade a torna manual.",
    responses={404: RESPOSTA_404, 422: RESPOSTA_422},
)
def editar_tarefa(task_id: TaskId, data: TaskUpdate, service: ServiceDep) -> Task:
    """Atualiza uma tarefa."""
    return service.update(task_id, data)


@router.delete(
    "/{task_id}",
    status_code=204,
    response_class=Response,
    summary="Remover tarefa",
    responses={404: RESPOSTA_404, 422: RESPOSTA_422},
)
def remover_tarefa(task_id: TaskId, service: ServiceDep) -> None:
    """Remove uma tarefa."""
    service.delete(task_id)
