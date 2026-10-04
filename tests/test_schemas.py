from datetime import datetime
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.schemas.task import (
    PRIORITY_FALLBACK_NOTICE,
    PrioritySource,
    TaskCreate,
    TaskOut,
    TaskPriority,
    TaskStatus,
    TaskUpdate,
)


def test_titulo_so_com_espacos_e_rejeitado() -> None:
    with pytest.raises(ValidationError) as exc:
        TaskCreate(title="   ")
    assert "O título não pode ficar em branco." in str(exc.value)


def test_titulo_com_100_caracteres_e_espacos_nas_pontas_e_aceito() -> None:
    task = TaskCreate(title="  " + "a" * 100 + "  ")
    assert task.title == "a" * 100


def test_titulo_com_101_caracteres_e_rejeitado() -> None:
    with pytest.raises(ValidationError):
        TaskCreate(title="a" * 101)


def test_descricao_com_501_caracteres_e_rejeitada() -> None:
    with pytest.raises(ValidationError):
        TaskCreate(title="x", description="a" * 501)


def test_create_rejeita_campos_extras() -> None:
    for extra in (
        {"priority": "alta"},
        {"status": "pendente"},
        {"priority_source": "manual"},
    ):
        with pytest.raises(ValidationError):
            TaskCreate(title="x", **extra)


def test_update_sem_campos_e_rejeitado() -> None:
    with pytest.raises(ValidationError):
        TaskUpdate()


def test_update_com_todos_os_campos_nulos_e_rejeitado() -> None:
    with pytest.raises(ValidationError):
        TaskUpdate(title=None, priority=None)


def test_update_status_invalido_e_rejeitado() -> None:
    with pytest.raises(ValidationError):
        TaskUpdate(status="invalido")


def test_update_aceita_prioridade_valida() -> None:
    assert TaskUpdate(priority="alta").priority is TaskPriority.ALTA


def test_update_prioridade_invalida_e_rejeitada() -> None:
    with pytest.raises(ValidationError):
        TaskUpdate(priority="urgentissima")


def test_update_rejeita_priority_source() -> None:
    with pytest.raises(ValidationError):
        TaskUpdate(priority_source="manual")


def _objeto(source: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        title="t",
        description=None,
        status="pendente",
        priority="media",
        priority_source=source,
        created_at=datetime(2026, 10, 4),
    )


def test_task_out_le_de_objeto_simples() -> None:
    out = TaskOut.model_validate(_objeto("jev"))
    assert out.status is TaskStatus.PENDENTE
    assert out.priority_source is PrioritySource.JEV


def test_priority_notice_so_para_fallback() -> None:
    assert TaskOut.model_validate(_objeto("fallback")).priority_notice == PRIORITY_FALLBACK_NOTICE
    assert TaskOut.model_validate(_objeto("jev")).priority_notice is None
    assert TaskOut.model_validate(_objeto("manual")).priority_notice is None
    assert "priority_notice" in TaskOut.model_validate(_objeto("jev")).model_dump()
