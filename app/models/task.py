"""Model ORM da tarefa."""

import enum
from datetime import UTC, datetime

from sqlalchemy import DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.schemas.task import PrioritySource, TaskPriority, TaskStatus


def _enum_values(enum_class: type[enum.Enum]) -> list[str]:
    return [member.value for member in enum_class]


def _now() -> datetime:
    return datetime.now(UTC)


class Task(Base):
    """Tarefa persistida na tabela `tasks`."""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(500), default=None)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, native_enum=False, length=20, values_callable=_enum_values),
        default=TaskStatus.PENDENTE,
    )
    priority: Mapped[TaskPriority] = mapped_column(
        Enum(TaskPriority, native_enum=False, length=20, values_callable=_enum_values)
    )
    priority_source: Mapped[PrioritySource] = mapped_column(
        Enum(PrioritySource, native_enum=False, length=20, values_callable=_enum_values)
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
