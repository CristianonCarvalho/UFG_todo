"""Ponto de entrada da API de tarefas."""

from fastapi import FastAPI

from app.core.errors import register_exception_handlers
from app.routers.tasks import router as tasks_router


def create_app() -> FastAPI:
    """Cria o aplicativo FastAPI com as rotas e os handlers de erro."""
    app = FastAPI(
        title="API de Tarefas",
        description=(
            "Micro-API de gerenciamento de tarefas com prioridade sugerida automaticamente. "
            "Os erros seguem um formato único, com mensagens em português."
        ),
        version="0.1.0",
    )
    register_exception_handlers(app)
    app.include_router(tasks_router)
    return app


app = create_app()
