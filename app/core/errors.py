"""Tratamento amigável de erros: exceções de domínio, formato único e handlers globais."""

import logging
import re
import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("app.errors")

FIELD_LABELS: dict[str, tuple[str, str]] = {
    "title": ("o", "título"),
    "description": ("a", "descrição"),
    "status": ("o", "status"),
    "priority": ("a", "prioridade"),
}

HTTP_MESSAGES: dict[int, tuple[str, str]] = {
    404: ("NAO_ENCONTRADO", "Não encontramos o que você procurou."),
    405: ("METODO_NAO_PERMITIDO", "Esta ação não é permitida aqui."),
}
DEFAULT_HTTP_MESSAGE = (
    "REQUISICAO_INVALIDA",
    "Não foi possível concluir essa solicitação. Confira e tente novamente.",
)

VALIDATION_MESSAGE = "Confira os campos destacados e tente novamente."
DATABASE_MESSAGE = "Não conseguimos acessar os dados agora. Tente novamente em instantes."
INTERNAL_MESSAGE = (
    "Algo deu errado do nosso lado. Tente novamente; "
    "se continuar, avise a equipe informando o código da requisição."
)


class ErrorDetail(BaseModel):
    """Problema em um campo específico."""

    campo: str
    mensagem: str


class ErrorBody(BaseModel):
    """Conteúdo de uma resposta de erro."""

    codigo: str
    mensagem: str
    detalhes: list[ErrorDetail] | None = None
    id_requisicao: str


class ErrorResponse(BaseModel):
    """Formato único de resposta de erro da API."""

    erro: ErrorBody


class AppError(Exception):
    """Erro de domínio com mensagem amigável e código HTTP."""

    def __init__(self, codigo: str, mensagem: str, status_code: int) -> None:
        """Cria o erro com código, mensagem para o usuário e status HTTP."""
        super().__init__(mensagem)
        self.codigo = codigo
        self.mensagem = mensagem
        self.status_code = status_code


class TaskNotFoundError(AppError):
    """Tarefa inexistente."""

    def __init__(self) -> None:
        """Cria o erro 404 de tarefa não encontrada."""
        super().__init__(
            "TAREFA_NAO_ENCONTRADA",
            "Não encontramos essa tarefa. Ela pode ter sido removida.",
            404,
        )


def _join_options(options: list[str]) -> str:
    if len(options) > 1:
        return ", ".join(options[:-1]) + " ou " + options[-1]
    return options[0]


def _field_name(loc: tuple[Any, ...]) -> str:
    parts = [str(part) for part in loc if part not in ("body", "query", "path")]
    return ".".join(parts) or "corpo"


def _translate(error: dict[str, Any]) -> ErrorDetail:
    tipo = error["type"]
    if tipo == "json_invalid":
        return ErrorDetail(campo="corpo", mensagem="O corpo da requisição não é um JSON válido.")

    campo = _field_name(tuple(error["loc"]))
    artigo, nome = FIELD_LABELS.get(campo, ("o", f"campo {campo}"))
    sujeito = f"{artigo.upper()} {nome}"
    feminino = artigo == "a"
    ctx = error.get("ctx") or {}

    if tipo == "missing":
        mensagem = f"{sujeito} é {'obrigatória' if feminino else 'obrigatório'}."
    elif tipo == "string_too_short":
        if ctx.get("min_length") == 1:
            mensagem = f"{sujeito} não pode ficar em branco."
        else:
            mensagem = f"{sujeito} tem poucos caracteres. Use pelo menos {ctx.get('min_length')}."
    elif tipo == "string_too_long":
        mensagem = f"{sujeito} tem caracteres demais. Use no máximo {ctx.get('max_length')}."
    elif tipo == "enum":
        opcoes = re.findall(r"'([^']+)'", str(ctx.get("expected", "")))
        if opcoes:
            sufixo = "inválida" if feminino else "inválido"
            mensagem = f"{nome.capitalize()} {sufixo}. Use: {_join_options(opcoes)}."
        else:
            mensagem = "Valor inválido."
    elif tipo == "extra_forbidden":
        mensagem = f'O campo "{campo}" não pode ser enviado aqui.'
    elif tipo == "value_error":
        mensagem = str(error["msg"]).removeprefix("Value error, ")
    else:
        mensagem = "Valor inválido."
    return ErrorDetail(campo=campo, mensagem=mensagem)


def _error_response(
    status_code: int,
    codigo: str,
    mensagem: str,
    request_id: str,
    detalhes: list[ErrorDetail] | None = None,
) -> JSONResponse:
    corpo = ErrorResponse(
        erro=ErrorBody(
            codigo=codigo, mensagem=mensagem, detalhes=detalhes, id_requisicao=request_id
        )
    )
    return JSONResponse(
        status_code=status_code, content=corpo.model_dump(mode="json", exclude_none=True)
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Registra os handlers globais que convertem falhas em respostas amigáveis."""

    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        request_id = str(uuid.uuid4())
        logger.info("Erro tratado codigo=%s id_requisicao=%s", exc.codigo, request_id)
        return _error_response(exc.status_code, exc.codigo, exc.mensagem, request_id)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        request_id = str(uuid.uuid4())
        detalhes = [_translate(dict(error)) for error in exc.errors()]
        logger.info("Dados inválidos id_requisicao=%s", request_id)
        return _error_response(422, "DADOS_INVALIDOS", VALIDATION_MESSAGE, request_id, detalhes)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        request_id = str(uuid.uuid4())
        codigo, mensagem = HTTP_MESSAGES.get(exc.status_code, DEFAULT_HTTP_MESSAGE)
        logger.info("Erro HTTP %s id_requisicao=%s", exc.status_code, request_id)
        return _error_response(exc.status_code, codigo, mensagem, request_id)

    @app.exception_handler(SQLAlchemyError)
    async def _database_error(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        request_id = str(uuid.uuid4())
        logger.error("Falha no banco id_requisicao=%s", request_id, exc_info=exc)
        return _error_response(503, "BANCO_INDISPONIVEL", DATABASE_MESSAGE, request_id)

    @app.exception_handler(Exception)
    async def _unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        request_id = str(uuid.uuid4())
        logger.error("Erro inesperado id_requisicao=%s", request_id, exc_info=exc)
        return _error_response(500, "ERRO_INTERNO", INTERNAL_MESSAGE, request_id)
