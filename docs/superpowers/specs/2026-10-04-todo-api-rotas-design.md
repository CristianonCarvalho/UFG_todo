# Micro-API To-Do — Ciclo 2: persistência, service, rotas e `main.py`

Data: 2026-10-04. Continua o spec `2026-10-04-todo-api-design.md` (ciclo 1, já entregue).
Ciclo 1 entregou: dependências, `Settings`, schemas, erros, classificador, testes, diagramas, ADRs, README e CI.
Este ciclo entrega a API funcionando de ponta a ponta.

## Objetivo

Persistir tarefas em SQLite, aplicar as regras de negócio no service, expor os endpoints
REST e subir o app com `uvicorn`, mantendo o formato único de erros em português e a
prioridade automática com fallback.

## Decisões deste ciclo

| Tema | Decisão |
|---|---|
| `DELETE /tasks/{id}` | Incluído (CRUD completo); responde 204 sem corpo |
| Esquema do banco | Migração inicial do Alembic; produção usa `alembic upgrade head`. Testes criam as tabelas com `Base.metadata.create_all` |
| Sessão | SQLAlchemy síncrono, uma sessão por requisição (dependência `get_db`), com `rollback` em falha |
| Rotas | Funções síncronas (`def`), pois o classificador usa `httpx.Client` síncrono; o FastAPI as executa em threadpool |
| Nova configuração | `database_url` em `Settings` (padrão `sqlite:///./tasks.db`; variável `DATABASE_URL`), e entra em `.env.example` e no README |
| Ordenação da listagem | Por `id` crescente. Sem paginação (fora do escopo) |
| Concluir uma tarefa já concluída | Idempotente: responde 200 com a tarefa, sem erro |
| Dependências novas | Nenhuma. Alembic e SQLAlchemy já estão fixados |
| Testes | Unitários (service com repository e classificador falsos; controllers com service falso) e de integração (`TestClient` + SQLite em arquivo temporário) |
| Idioma e docstrings | Português, estilo Google, como no ciclo 1 |

## Arquivos

Código (`app/`):
- `db.py`: `Base`, `build_engine(settings)`, `build_session_factory(engine)`, dependência `get_db`.
- `models/task.py`: model ORM `Task`.
- `repositories/task_repository.py`: `TaskRepository`.
- `services/task_service.py`: `TaskService`.
- `routers/tasks.py`: controller com os 6 endpoints.
- `dependencies.py`: `get_task_service`, `get_classifier`.
- `main.py`: `create_app()` e `app`.
- `core/config.py`: acrescenta `database_url`.

Migração: `alembic.ini`, `migrations/env.py`, `migrations/script.py.mako`,
`migrations/versions/0001_cria_tabela_tasks.py`.

Testes: `tests/unit/test_task_service.py`, `tests/unit/test_tasks_router.py`,
`tests/integration/test_tasks_api.py`, `tests/integration/conftest.py`.
Os testes do ciclo 1 em `tests/` permanecem onde estão.

Docs: atualizar `README.md`, `docs/decisoes-tecnicas.md` e `.env.example`;
`docs/arquitetura.md` já descreve o desenho e só muda se a implementação divergir.
`.gitignore`: acrescentar `tasks.db`, `.coverage`, `.meister/`.

## Modelo ORM (`app/models/task.py`)

Tabela `tasks`: `id` (inteiro, chave primária, autoincremento), `title` (texto, 100),
`description` (texto, até 500, nulo), `status` (texto, valores de `TaskStatus`, padrão
`pendente`), `priority` (texto, valores de `TaskPriority`), `priority_source` (texto,
valores de `PrioritySource`), `created_at` (data e hora com fuso UTC, preenchida na criação).
Enums gravados como texto (`native_enum=False`), com os valores em português dos enums
do ciclo 1. O model deve ser lido por `TaskOut` (`from_attributes=True`).

## Repository (`app/repositories/task_repository.py`)

`TaskRepository(session: Session)`, sem regras de negócio e sem `commit` fora dos métodos
de escrita:
- `add(task: Task) -> Task`: insere, faz `commit` e `refresh`.
- `get(task_id: int) -> Task | None`.
- `list(status: TaskStatus | None) -> list[Task]`: filtra se `status` vier; ordena por `id`.
- `update(task: Task) -> Task`: `commit` e `refresh`.
- `delete(task: Task) -> None`: remove e faz `commit`.
Em `SQLAlchemyError`, faz `rollback` e relança (o handler global devolve 503).

## Service (`app/services/task_service.py`)

`TaskService(repository, classifier: PriorityClassifier)`:
- `create(data: TaskCreate) -> Task`: status `pendente`; chama `classifier.classify(title, description)`;
  grava `priority` e `priority_source` com o resultado (`jev` ou `fallback`).
- `get(task_id) -> Task`: levanta `TaskNotFoundError` se não existir.
- `list(status: TaskStatus | None) -> list[Task]`.
- `update(task_id, data: TaskUpdate) -> Task`: aplica só os campos informados. Se `priority`
  vier, grava a prioridade e define `priority_source = manual`. Não chama o classificador.
  Editar título ou descrição não reclassifica nem altera `priority_source`.
- `complete(task_id) -> Task`: status `concluida`; idempotente.
- `delete(task_id) -> None`: levanta `TaskNotFoundError` se não existir.
Uma prioridade `manual` nunca é sobrescrita pelo classificador.

## Controller (`app/routers/tasks.py`)

Prefixo `/tasks`, `response_model=TaskOut`, documentação OpenAPI em português.

| Endpoint | Sucesso | Erros |
|---|---|---|
| `POST /tasks` (`TaskCreate`) | 201 | 422 |
| `GET /tasks?status=` | 200, lista | 422 (status inválido) |
| `GET /tasks/{id}` | 200 | 404 |
| `PATCH /tasks/{id}` (`TaskUpdate`) | 200 | 404, 422 |
| `PATCH /tasks/{id}/complete` | 200 | 404 |
| `DELETE /tasks/{id}` | 204 | 404 |

As respostas de erro documentadas no OpenAPI usam `ErrorResponse`. O controller só valida,
delega ao service e devolve o código HTTP; não contém regra de negócio.

## `main.py` e dependências

`create_app()` cria o `FastAPI` (título e descrição em português), registra
`register_exception_handlers` e inclui o router. `app = create_app()` permite
`uvicorn app.main:app`. `get_task_service` monta `TaskService` com `TaskRepository(get_db)`
e `JevPriorityClassifier(get_settings())`; `get_classifier` fica separado para ser
sobrescrito nos testes (`app.dependency_overrides`). Nenhum teste faz chamada real à rede.

## Tratamento de erros

Reutiliza o ciclo 1: `TaskNotFoundError` vira 404; `RequestValidationError` vira 422;
`SQLAlchemyError` vira 503; qualquer outra falha vira 500, sempre no formato
`{"erro": {...}}`. Falha do Jev nunca vira erro: o fallback cria a tarefa e `priority_notice`
avisa. Corpo malformado, `id` não numérico e `status` inválido na query devem gerar 422
amigável, nunca 500.

## Testes

Unitários do service: criação com Jev (`source=jev`), com fallback (`source=fallback`),
status inicial `pendente`, edição de prioridade grava `manual` e não chama o classificador,
edição de título preserva a origem, `complete` idempotente, `get` e `delete` de id
inexistente levantam `TaskNotFoundError`.
Unitários do controller: service falso; códigos HTTP e formato de erro.
Integração (`TestClient`, SQLite temporário, classificador sobrescrito): ciclo completo
criar → listar com e sem filtro → editar prioridade → concluir → remover; 404 em cada
rota por id; 422 (corpo vazio, título em branco, prioridade inválida, status inválido na
query, id não numérico, JSON malformado); persistência entre requisições; `priority_notice`
presente só com `fallback`; prioridade manual preservada após editar o título; resposta 503
quando o banco falha (ex.: engine apontando para caminho inválido).
Cobertura total mínima de 90%; `ruff`, `ruff format`, `mypy` e `pip check` limpos.

## Verificação

Venv; `pip install -r requirements-dev.txt`; `alembic upgrade head` em banco temporário;
`pytest --cov=app`; `ruff check app tests`; `ruff format --check app tests`; `mypy app`;
subir `uvicorn app.main:app` e confirmar `GET /docs` e `GET /openapi.json`; exercitar os 6
endpoints com `curl`, mostrando os JSONs de sucesso e de erro. Chamada real ao Jev
só com autorização explícita do usuário, usando a chave que ele já tem no `.env`; sem
autorização, é registrada como pendência. README atualizado só com comandos executados.

## Notas para o plano (lições do ciclo 1)

- Formato do plano para o `meister plan import`: um arquivo por linha em `**Files:**`, sem
  texto entre parênteses nas linhas de arquivo, e um bloco `**Interfaces:**` em toda tarefa.
- `--deps files` não detecta dependências entre tarefas; declará-las manualmente em
  `plano.json` (por exemplo: model → repository → service → router → `main` → integração).
- Portão do Meister: manter `meister.config.yaml` com `commands` explícito; a verificação
  real é feita pelo arquiteto ao final de cada lote.
- Conferir no resultado dos workers o que o plano pedia literalmente (no ciclo 1, o README
  de um worker ignorou o texto exigido).
- O `black` não roda no Python 3.12.5 local; usar `ruff format --check` como equivalente.

## Fora do escopo

Autenticação, cache, filas, Docker, deploy, outros bancos, paginação, reclassificação
automática ao editar título ou descrição, frontend, internacionalização.
