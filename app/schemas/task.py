"""Schemas Pydantic de tarefas: entrada, atualização e saída."""

from datetime import datetime
from enum import StrEnum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)

PRIORITY_FALLBACK_NOTICE = (
    "Não foi possível classificar a prioridade automaticamente agora, "
    "então usamos uma estimativa. Você pode ajustá-la quando quiser."
)


class TaskStatus(StrEnum):
    """Situação de uma tarefa."""

    PENDENTE = "pendente"
    CONCLUIDA = "concluida"


class TaskPriority(StrEnum):
    """Prioridade de uma tarefa."""

    BAIXA = "baixa"
    MEDIA = "media"
    ALTA = "alta"


class PrioritySource(StrEnum):
    """Origem da prioridade de uma tarefa."""

    JEV = "jev"
    FALLBACK = "fallback"
    MANUAL = "manual"


def _reject_blank(value: object) -> object:
    if isinstance(value, str) and not value.strip():
        raise ValueError("O título não pode ficar em branco.")
    return value


class TaskCreate(BaseModel):
    """Dados para criar uma tarefa."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)

    @field_validator("title", mode="before")
    @classmethod
    def _title_not_blank(cls, value: object) -> object:
        return _reject_blank(value)


class TaskUpdate(BaseModel):
    """Dados para atualizar uma tarefa; ao menos um campo deve ser informado."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    status: TaskStatus | None = None
    priority: TaskPriority | None = None

    @field_validator("title", mode="before")
    @classmethod
    def _title_not_blank(cls, value: object) -> object:
        return _reject_blank(value)

    @model_validator(mode="after")
    def _require_some_field(self) -> "TaskUpdate":
        if all(getattr(self, name) is None for name in type(self).model_fields):
            raise ValueError("Informe ao menos um campo para atualizar.")
        return self


class TaskOut(BaseModel):
    """Tarefa devolvida pela API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority
    priority_source: PrioritySource
    created_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def priority_notice(self) -> str | None:
        """Aviso amigável quando a prioridade veio do fallback."""
        if self.priority_source is PrioritySource.FALLBACK:
            return PRIORITY_FALLBACK_NOTICE
        return None
