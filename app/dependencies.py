"""Dependências injetadas nas rotas."""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db import get_db
from app.repositories.task_repository import TaskRepository
from app.services.priority_classifier import JevPriorityClassifier, PriorityClassifier
from app.services.task_service import TaskService


@lru_cache
def _build_classifier() -> JevPriorityClassifier:
    return JevPriorityClassifier(get_settings())


def get_classifier() -> PriorityClassifier:
    """Devolve o classificador de prioridade do processo."""
    return _build_classifier()


def get_task_service(
    session: Annotated[Session, Depends(get_db)],
    classifier: Annotated[PriorityClassifier, Depends(get_classifier)],
) -> TaskService:
    """Monta o service da requisição com o repository e o classificador."""
    return TaskService(TaskRepository(session), classifier)
