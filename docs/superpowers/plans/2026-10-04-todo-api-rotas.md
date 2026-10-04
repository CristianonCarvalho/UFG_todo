# Micro-API To-Do — Ciclo 2: persistência, service, rotas e main — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar a API de tarefas funcionando de ponta a ponta: model ORM, migração Alembic, repository, service, 6 endpoints REST, `main.py`, testes unitários e de integração, e documentação atualizada.

**Architecture:** Camadas controller (router) → service → repository sobre SQLAlchemy síncrono e SQLite. O service usa o classificador de prioridade do ciclo 1 e o repository é acessado por um `Protocol`, o que permite testar o service sem banco. Os handlers de erro do ciclo 1 cobrem todas as falhas.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x, Alembic, Pydantic v2, pytest, ruff, mypy.

**Spec:** `docs/superpowers/specs/2026-10-04-todo-api-rotas-design.md` (continua `2026-10-04-todo-api-design.md`).

## Global Constraints

- Python `>=3.12,<3.13`; nenhuma dependência nova (Alembic e SQLAlchemy já estão fixados).
- Pydantic v2 e SQLAlchemy 2.x (`Mapped`, `mapped_column`, `select`); `str | None`, nunca `Optional`.
- Docstrings em português, estilo Google, em módulos, classes e funções públicas.
- Mensagens ao usuário em português do Brasil; nenhum detalhe técnico (stack trace, SQL, caminho de arquivo, nome de exceção) nas respostas.
- Nunca registrar em log chave de API, título nem descrição.
- Testes sem rede. Cobertura total mínima de 90%.
- Qualidade: `ruff check app tests`, `ruff format --check app tests` (equivalente ao `black`, que não roda no Python 3.12.5 local) e `mypy app` limpos. Linhas com até 100 caracteres, no estilo `black`.
- Os métodos de listagem se chamam `list_tasks` (e não `list`) para não sombrear o `list` embutido nas anotações.
- Em worktree do Meister não há `.venv`: use `/Users/cristianocarvalho/Documents/UFG_TODO/.venv/bin/` no lugar de `.venv/bin/` nos comandos abaixo.
- Commits pequenos, Conventional Commits em português, com o trailer `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`. Sem push.
- Fora do escopo: autenticação, cache, filas, Docker, deploy, outros bancos, paginação, reclassificação automática ao editar título ou descrição, frontend.

## Review Focus

1. `id` fora do intervalo do SQLite (ex.: `99999999999999999999`), zero, negativo ou não numérico deve gerar 422 amigável, nunca 500. (Tasks 6 e 7)
2. Editar só o título de uma tarefa `manual` mantém `manual` e a prioridade; editar a prioridade para o mesmo valor ainda marca `manual`. (Tasks 5 e 7)
3. Falha do banco gera 503 amigável sem vazar caminho nem SQL, e a sessão seguinte continua utilizável. (Tasks 4 e 7)
4. `status` com maiúsculas na query (`Pendente`) gera 422 listando as opções válidas. (Task 7)
5. `PATCH` com `{"priority": null}` ou `description` acima de 500 caracteres gera 422 amigável; remover duas vezes gera 404 na segunda. (Task 7)

---

### Task 1: Configuração do banco e arquivos de ambiente

**Files:**
- Modify: `app/core/config.py`
- Modify: `.env.example`
- Modify: `.gitignore`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `Settings.database_url: str` (padrão `"sqlite:///./tasks.db"`, variável `DATABASE_URL`).

- [ ] **Step 1: Escrever o teste que falha** — acrescente ao final de `tests/test_config.py`

```python
def test_database_url_padrao_e_sobrescrita(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert Settings(_env_file=None).database_url == "sqlite:///./tasks.db"
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./outro.db")
    assert Settings(_env_file=None).database_url == "sqlite:///./outro.db"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/pytest tests/test_config.py -v`
Expected: FAIL com `AttributeError` em `database_url`.

- [ ] **Step 3: Implementar** — em `app/core/config.py`, troque a docstring da classe por `"""Configurações da aplicação: banco de dados e classificador de prioridade."""` e acrescente o campo logo após `jev_min_confidence`:

```python
    database_url: str = "sqlite:///./tasks.db"
```

- [ ] **Step 4: Atualizar `.env.example`** — acrescente ao final

```dotenv
DATABASE_URL=sqlite:///./tasks.db
```

- [ ] **Step 5: Atualizar `.gitignore`** — acrescente ao final

```gitignore

# Banco local, cobertura e estado do Meister
tasks.db
.coverage
.meister/
```

- [ ] **Step 6: Rodar e ver passar**

Run: `.venv/bin/pytest tests/test_config.py -v && .venv/bin/ruff check app tests && .venv/bin/mypy app`
Expected: 4 passed; ferramentas limpas.

- [ ] **Step 7: Commit**

```bash
git add app/core/config.py .env.example .gitignore tests/test_config.py
git commit -m "feat: adiciona database_url às configurações" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Conexão com o banco e model ORM

**Files:**
- Create: `app/db.py`
- Create: `app/models/__init__.py`
- Create: `app/models/task.py`
- Create: `tests/unit/conftest.py`
- Test: `tests/unit/test_task_model.py`

**Interfaces:**
- Consumes: `Settings.database_url` (Task 1); `TaskStatus`, `TaskPriority`, `PrioritySource` de `app.schemas.task`.
- Produces: `Base` (declarativa), `build_engine(settings: Settings) -> Engine`, `build_session_factory(engine: Engine) -> sessionmaker[Session]`, `get_session_factory() -> sessionmaker[Session]` (cache), `get_db() -> Iterator[Session]`; model `Task(id, title, description, status, priority, priority_source, created_at)`; fixture de teste `session` (SQLite em memória com as tabelas criadas).

- [ ] **Step 1: Criar a fixture compartilhada** — `tests/unit/conftest.py`

```python
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.db import Base, build_session_factory


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = build_session_factory(engine)()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()
```

- [ ] **Step 2: Escrever o teste que falha** — `tests/unit/test_task_model.py`

```python
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.task import Task
from app.schemas.task import PrioritySource, TaskPriority, TaskStatus


def test_persiste_com_valores_padrao(session: Session) -> None:
    tarefa = Task(
        title="Escrever relatório",
        priority=TaskPriority.MEDIA,
        priority_source=PrioritySource.JEV,
    )
    session.add(tarefa)
    session.commit()
    session.refresh(tarefa)
    assert tarefa.id == 1
    assert tarefa.status is TaskStatus.PENDENTE
    assert tarefa.description is None
    assert tarefa.created_at is not None


def test_enums_sao_gravados_como_texto_em_portugues(session: Session) -> None:
    session.add(
        Task(
            title="t",
            status=TaskStatus.CONCLUIDA,
            priority=TaskPriority.ALTA,
            priority_source=PrioritySource.FALLBACK,
        )
    )
    session.commit()
    linha = session.execute(text("select status, priority, priority_source from tasks")).one()
    assert tuple(linha) == ("concluida", "alta", "fallback")
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `.venv/bin/pytest tests/unit -v`
Expected: FAIL com `ModuleNotFoundError: app.db`.

- [ ] **Step 4: Implementar `app/db.py`**

```python
"""Conexão com o banco SQLite e sessões do SQLAlchemy."""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import Settings, get_settings


class Base(DeclarativeBase):
    """Base declarativa dos models ORM."""


def build_engine(settings: Settings) -> Engine:
    """Cria o engine do banco; no SQLite, permite o uso em várias threads."""
    connect_args: dict[str, bool] = {}
    if settings.database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(settings.database_url, connect_args=connect_args)


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Cria a fábrica de sessões; os objetos continuam acessíveis após o commit."""
    return sessionmaker(bind=engine, expire_on_commit=False)


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    """Devolve a fábrica de sessões do processo, criada uma única vez."""
    return build_session_factory(build_engine(get_settings()))


def get_db() -> Iterator[Session]:
    """Entrega uma sessão por requisição, com rollback em caso de falha."""
    session = get_session_factory()()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
```

- [ ] **Step 5: Implementar o model** — `app/models/task.py`

```python
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
```

`app/models/__init__.py`:

```python
"""Models ORM da aplicação."""

from app.models.task import Task

__all__ = ["Task"]
```

- [ ] **Step 6: Rodar e ver passar**

Run: `.venv/bin/pytest tests/unit -v && .venv/bin/ruff check app tests && .venv/bin/ruff format --check app tests && .venv/bin/mypy app`
Expected: 2 passed; ferramentas limpas. Se o `mypy` reclamar de `Enum(...)`, ajuste só a tipagem (por exemplo `# type: ignore[...]` com o código exato reportado), sem mudar o comportamento.

- [ ] **Step 7: Commit**

```bash
git add app/db.py app/models tests/unit/conftest.py tests/unit/test_task_model.py
git commit -m "feat: adiciona conexão com o banco e model Task" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Migração inicial do Alembic

**Files:**
- Create: `alembic.ini`
- Create: `migrations/env.py`
- Create: `migrations/script.py.mako`
- Create: `migrations/versions/0001_cria_tabela_tasks.py`
- Test: `tests/integration/test_migration.py`

**Interfaces:**
- Consumes: `Base`, `Task` (Task 2); `get_settings().database_url` (Task 1).
- Produces: `alembic upgrade head` cria a tabela `tasks`; `alembic downgrade base` a remove.

- [ ] **Step 1: Escrever o teste que falha** — `tests/integration/test_migration.py`

```python
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from app.models.task import Task
from app.schemas.task import PrioritySource, TaskPriority, TaskStatus

RAIZ = Path(__file__).resolve().parents[2]


def _config(url: str) -> Config:
    cfg = Config(str(RAIZ / "alembic.ini"))
    cfg.set_main_option("script_location", str(RAIZ / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def test_migracao_cria_tabela_compativel_com_o_model(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'migracao.db'}"
    cfg = _config(url)
    command.upgrade(cfg, "head")

    engine = create_engine(url)
    colunas = {coluna["name"] for coluna in inspect(engine).get_columns("tasks")}
    assert colunas == set(Task.__table__.columns.keys())

    with Session(engine) as session:
        session.add(Task(title="t", priority=TaskPriority.MEDIA, priority_source=PrioritySource.JEV))
        session.commit()
        assert session.query(Task).one().status is TaskStatus.PENDENTE

    command.downgrade(cfg, "base")
    assert "tasks" not in inspect(engine).get_table_names()
    engine.dispose()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/pytest tests/integration/test_migration.py -v`
Expected: FAIL (não existe `alembic.ini` nem `migrations/`).

- [ ] **Step 3: Criar `alembic.ini`**

```ini
[alembic]
script_location = migrations
prepend_sys_path = .
```

- [ ] **Step 4: Criar `migrations/env.py`**

```python
"""Ambiente de execução das migrações do Alembic."""

from alembic import context
from sqlalchemy import engine_from_config, pool

import app.models  # noqa: F401
from app.core.config import get_settings
from app.db import Base

config = context.config
target_metadata = Base.metadata


def _url() -> str:
    return config.get_main_option("sqlalchemy.url") or get_settings().database_url


def run_migrations_offline() -> None:
    """Gera o SQL das migrações sem conectar ao banco."""
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Aplica as migrações conectando ao banco."""
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = _url()
    connectable = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 5: Criar `migrations/script.py.mako`**

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 6: Criar `migrations/versions/0001_cria_tabela_tasks.py`**

```python
"""Cria a tabela tasks.

Revision ID: 0001
Revises:
Create Date: 2026-10-04
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _enum(nome: str, *valores: str) -> sa.Enum:
    return sa.Enum(*valores, name=nome, native_enum=False, length=20)


def upgrade() -> None:
    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("title", sa.String(100), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("status", _enum("taskstatus", "pendente", "concluida"), nullable=False),
        sa.Column("priority", _enum("taskpriority", "baixa", "media", "alta"), nullable=False),
        sa.Column(
            "priority_source",
            _enum("prioritysource", "jev", "fallback", "manual"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("tasks")
```

- [ ] **Step 7: Rodar e ver passar**

Run: `.venv/bin/pytest tests/integration/test_migration.py -v && .venv/bin/ruff check app tests && .venv/bin/ruff format --check app tests`
Expected: 1 passed; ferramentas limpas.

- [ ] **Step 8: Commit**

```bash
git add alembic.ini migrations tests/integration/test_migration.py
git commit -m "feat: adiciona migração inicial da tabela tasks" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Repository

**Files:**
- Create: `app/repositories/__init__.py`
- Create: `app/repositories/task_repository.py`
- Test: `tests/unit/test_task_repository.py`

**Interfaces:**
- Consumes: `Task` (Task 2), fixture `session` (Task 2), `TaskStatus`.
- Produces: `TaskRepository(session: Session)` com `add(task: Task) -> Task`, `get(task_id: int) -> Task | None`, `list_tasks(status: TaskStatus | None = None) -> list[Task]`, `update(task: Task) -> Task`, `delete(task: Task) -> None`.

- [ ] **Step 1: Escrever os testes que falham** — `tests/unit/test_task_repository.py`

```python
import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.task import Task
from app.repositories.task_repository import TaskRepository
from app.schemas.task import PrioritySource, TaskPriority, TaskStatus


def nova(titulo: str = "t", status: TaskStatus = TaskStatus.PENDENTE) -> Task:
    return Task(
        title=titulo,
        status=status,
        priority=TaskPriority.MEDIA,
        priority_source=PrioritySource.JEV,
    )


def test_add_e_get(session: Session) -> None:
    repo = TaskRepository(session)
    salva = repo.add(nova("primeira"))
    assert salva.id == 1
    assert salva.created_at is not None
    assert repo.get(1) is salva


def test_get_inexistente_devolve_none(session: Session) -> None:
    assert TaskRepository(session).get(999) is None


def test_list_tasks_ordena_por_id_e_filtra_por_status(session: Session) -> None:
    repo = TaskRepository(session)
    repo.add(nova("a"))
    repo.add(nova("b", TaskStatus.CONCLUIDA))
    repo.add(nova("c"))
    assert [t.title for t in repo.list_tasks()] == ["a", "b", "c"]
    assert [t.title for t in repo.list_tasks(TaskStatus.PENDENTE)] == ["a", "c"]
    assert [t.title for t in repo.list_tasks(TaskStatus.CONCLUIDA)] == ["b"]


def test_update_persiste_alteracoes(session: Session) -> None:
    repo = TaskRepository(session)
    tarefa = repo.add(nova("antes"))
    tarefa.title = "depois"
    repo.update(tarefa)
    session.expire_all()
    assert repo.get(tarefa.id).title == "depois"  # type: ignore[union-attr]


def test_delete_remove_a_tarefa(session: Session) -> None:
    repo = TaskRepository(session)
    tarefa = repo.add(nova())
    repo.delete(tarefa)
    assert repo.get(tarefa.id) is None


def test_falha_de_banco_faz_rollback_e_a_sessao_continua_utilizavel(session: Session) -> None:
    repo = TaskRepository(session)
    invalida = Task(title=None, priority=TaskPriority.MEDIA, priority_source=PrioritySource.JEV)
    with pytest.raises(SQLAlchemyError):
        repo.add(invalida)
    valida = repo.add(nova("depois do erro"))
    assert valida.id is not None
    assert [t.title for t in repo.list_tasks()] == ["depois do erro"]
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/pytest tests/unit/test_task_repository.py -v`
Expected: FAIL com `ModuleNotFoundError: app.repositories`.

- [ ] **Step 3: Implementar** — `app/repositories/__init__.py`: `"""Repositories de acesso ao banco."""`; `app/repositories/task_repository.py`:

```python
"""Acesso ao banco para tarefas, sem regras de negócio."""

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.task import Task
from app.schemas.task import TaskStatus


class TaskRepository:
    """Lê e grava tarefas no banco por meio de uma sessão do SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        """Cria o repository sobre a sessão da requisição."""
        self._session = session

    def add(self, task: Task) -> Task:
        """Insere a tarefa e devolve a versão gravada."""
        return self._persist(task)

    def update(self, task: Task) -> Task:
        """Grava as alterações da tarefa e devolve a versão gravada."""
        return self._persist(task)

    def get(self, task_id: int) -> Task | None:
        """Busca uma tarefa pelo id; devolve `None` se não existir."""
        return self._session.get(Task, task_id)

    def list_tasks(self, status: TaskStatus | None = None) -> list[Task]:
        """Lista as tarefas por id, filtrando por status quando informado."""
        consulta = select(Task).order_by(Task.id)
        if status is not None:
            consulta = consulta.where(Task.status == status)
        return list(self._session.scalars(consulta))

    def delete(self, task: Task) -> None:
        """Remove a tarefa do banco."""
        try:
            self._session.delete(task)
            self._session.commit()
        except SQLAlchemyError:
            self._session.rollback()
            raise

    def _persist(self, task: Task) -> Task:
        try:
            self._session.add(task)
            self._session.commit()
            self._session.refresh(task)
        except SQLAlchemyError:
            self._session.rollback()
            raise
        return task
```

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/bin/pytest tests/unit/test_task_repository.py -v && .venv/bin/ruff check app tests && .venv/bin/ruff format --check app tests && .venv/bin/mypy app`
Expected: 6 passed; ferramentas limpas.

- [ ] **Step 5: Commit**

```bash
git add app/repositories tests/unit/test_task_repository.py
git commit -m "feat: adiciona TaskRepository" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Service

**Files:**
- Create: `app/services/task_service.py`
- Test: `tests/unit/test_task_service.py`

**Interfaces:**
- Consumes: `Task` (Task 2), `PriorityClassifier`, `PriorityResult` (ciclo 1), `TaskCreate`, `TaskUpdate`, `TaskStatus`, `PrioritySource` e `TaskNotFoundError` (ciclo 1).
- Produces: `TaskRepositoryPort` (`Protocol` com `add`, `get`, `list_tasks`, `update`, `delete`, mesmas assinaturas do `TaskRepository`) e `TaskService(repository: TaskRepositoryPort, classifier: PriorityClassifier)` com `create(data: TaskCreate) -> Task`, `get(task_id: int) -> Task`, `list_tasks(status: TaskStatus | None = None) -> list[Task]`, `update(task_id: int, data: TaskUpdate) -> Task`, `complete(task_id: int) -> Task`, `delete(task_id: int) -> None`.

- [ ] **Step 1: Escrever os testes que falham** — `tests/unit/test_task_service.py`

```python
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
    def __init__(self) -> None:
        self.tasks: dict[int, Task] = {}
        self._next_id = 1

    def add(self, task: Task) -> Task:
        task.id = self._next_id
        task.created_at = datetime(2026, 10, 4)
        self.tasks[task.id] = task
        self._next_id += 1
        return task

    def get(self, task_id: int) -> Task | None:
        return self.tasks.get(task_id)

    def list_tasks(self, status: TaskStatus | None = None) -> list[Task]:
        itens = sorted(self.tasks.values(), key=lambda t: t.id)
        return [t for t in itens if status is None or t.status == status]

    def update(self, task: Task) -> Task:
        self.tasks[task.id] = task
        return task

    def delete(self, task: Task) -> None:
        del self.tasks[task.id]


class FakeClassifier:
    def __init__(self) -> None:
        self.result = PriorityResult(TaskPriority.ALTA, PrioritySource.JEV)
        self.calls: list[tuple[str, str | None]] = []

    def classify(self, title: str, description: str | None) -> PriorityResult:
        self.calls.append((title, description))
        return self.result


@pytest.fixture
def classifier() -> FakeClassifier:
    return FakeClassifier()


@pytest.fixture
def service(classifier: FakeClassifier) -> TaskService:
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
def test_id_inexistente_levanta_tarefa_nao_encontrada(
    service: TaskService, operacao: str
) -> None:
    with pytest.raises(TaskNotFoundError):
        if operacao == "update":
            service.update(999, TaskUpdate(title="x"))
        else:
            getattr(service, operacao)(999)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/pytest tests/unit/test_task_service.py -v`
Expected: FAIL com `ModuleNotFoundError: app.services.task_service`.

- [ ] **Step 3: Implementar** — `app/services/task_service.py`

```python
"""Regras de negócio das tarefas."""

from typing import Protocol

from app.core.errors import TaskNotFoundError
from app.models.task import Task
from app.schemas.task import PrioritySource, TaskCreate, TaskStatus, TaskUpdate
from app.services.priority_classifier import PriorityClassifier


class TaskRepositoryPort(Protocol):
    """Operações de persistência que o service precisa."""

    def add(self, task: Task) -> Task:
        """Insere a tarefa e a devolve gravada."""
        ...

    def get(self, task_id: int) -> Task | None:
        """Busca uma tarefa pelo id."""
        ...

    def list_tasks(self, status: TaskStatus | None = None) -> list[Task]:
        """Lista as tarefas, com filtro opcional de status."""
        ...

    def update(self, task: Task) -> Task:
        """Grava as alterações da tarefa."""
        ...

    def delete(self, task: Task) -> None:
        """Remove a tarefa."""
        ...


class TaskService:
    """Aplica as regras de negócio sobre o repository e o classificador."""

    def __init__(self, repository: TaskRepositoryPort, classifier: PriorityClassifier) -> None:
        """Cria o service com o repository e o classificador de prioridade."""
        self._repository = repository
        self._classifier = classifier

    def create(self, data: TaskCreate) -> Task:
        """Cria a tarefa como pendente, com a prioridade sugerida pelo classificador."""
        resultado = self._classifier.classify(data.title, data.description)
        tarefa = Task(
            title=data.title,
            description=data.description,
            status=TaskStatus.PENDENTE,
            priority=resultado.priority,
            priority_source=resultado.source,
        )
        return self._repository.add(tarefa)

    def get(self, task_id: int) -> Task:
        """Devolve a tarefa ou levanta `TaskNotFoundError`."""
        tarefa = self._repository.get(task_id)
        if tarefa is None:
            raise TaskNotFoundError()
        return tarefa

    def list_tasks(self, status: TaskStatus | None = None) -> list[Task]:
        """Lista as tarefas, filtrando por status quando informado."""
        return self._repository.list_tasks(status)

    def update(self, task_id: int, data: TaskUpdate) -> Task:
        """Aplica só os campos informados; editar a prioridade a marca como manual."""
        tarefa = self.get(task_id)
        if data.title is not None:
            tarefa.title = data.title
        if data.description is not None:
            tarefa.description = data.description
        if data.status is not None:
            tarefa.status = data.status
        if data.priority is not None:
            tarefa.priority = data.priority
            tarefa.priority_source = PrioritySource.MANUAL
        return self._repository.update(tarefa)

    def complete(self, task_id: int) -> Task:
        """Marca a tarefa como concluída; repetir a operação não gera erro."""
        tarefa = self.get(task_id)
        tarefa.status = TaskStatus.CONCLUIDA
        return self._repository.update(tarefa)

    def delete(self, task_id: int) -> None:
        """Remove a tarefa ou levanta `TaskNotFoundError`."""
        self._repository.delete(self.get(task_id))
```

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/bin/pytest tests/unit/test_task_service.py -v && .venv/bin/ruff check app tests && .venv/bin/ruff format --check app tests && .venv/bin/mypy app`
Expected: 14 passed (considerando os 4 parâmetros); ferramentas limpas.

- [ ] **Step 5: Commit**

```bash
git add app/services/task_service.py tests/unit/test_task_service.py
git commit -m "feat: adiciona TaskService com as regras de negócio" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Controller e dependências

**Files:**
- Create: `app/dependencies.py`
- Create: `app/routers/__init__.py`
- Create: `app/routers/tasks.py`
- Test: `tests/unit/test_tasks_router.py`

**Interfaces:**
- Consumes: `TaskService` (Task 5), `TaskRepository` (Task 4), `get_db` (Task 2), `JevPriorityClassifier`, `PriorityClassifier`, `get_settings`, `ErrorResponse`, `register_exception_handlers`, `TaskOut`, `TaskCreate`, `TaskUpdate`, `TaskStatus`.
- Produces: `get_classifier() -> PriorityClassifier`, `get_task_service(...) -> TaskService` (ambos usados em `dependency_overrides`) e `router` (prefixo `/tasks`) com os 6 endpoints.

- [ ] **Step 1: Escrever os testes que falham** — `tests/unit/test_tasks_router.py`

```python
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
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/pytest tests/unit/test_tasks_router.py -v`
Expected: FAIL com `ModuleNotFoundError: app.dependencies`.

- [ ] **Step 3: Implementar `app/dependencies.py`**

```python
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
```

- [ ] **Step 4: Implementar o controller** — `app/routers/__init__.py`: `"""Rotas da API."""`; `app/routers/tasks.py`:

```python
"""Controller das tarefas: valida a entrada, delega ao service e devolve o código HTTP."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

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
    summary="Remover tarefa",
    responses={404: RESPOSTA_404, 422: RESPOSTA_422},
)
def remover_tarefa(task_id: TaskId, service: ServiceDep) -> None:
    """Remove uma tarefa."""
    service.delete(task_id)
```

- [ ] **Step 5: Rodar e ver passar**

Run: `.venv/bin/pytest tests/unit/test_tasks_router.py -v && .venv/bin/ruff check app tests && .venv/bin/ruff format --check app tests && .venv/bin/mypy app`
Expected: todos passam; ferramentas limpas. Se o `DELETE` com 204 acusar erro do FastAPI sobre corpo, adicione `response_class=Response` (de `fastapi`) ao decorador e mantenha o retorno `None`.

- [ ] **Step 6: Commit**

```bash
git add app/dependencies.py app/routers tests/unit/test_tasks_router.py
git commit -m "feat: adiciona rotas de tarefas e dependências" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 7: `main.py` e testes de integração

**Files:**
- Create: `app/main.py`
- Create: `tests/integration/conftest.py`
- Test: `tests/integration/test_tasks_api.py`

**Interfaces:**
- Consumes: `router` e `get_classifier`, `get_task_service` (Task 6), `get_db`, `Base`, `build_session_factory` (Task 2), `register_exception_handlers`, `PriorityResult`.
- Produces: `create_app() -> FastAPI` e `app`; fixtures de integração `classifier` (falso, configurável), `client` (SQLite temporário) e `client_banco_quebrado`.

- [ ] **Step 1: Criar as fixtures** — `tests/integration/conftest.py`

```python
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401
from app.db import Base, build_session_factory, get_db
from app.dependencies import get_classifier
from app.main import create_app
from app.schemas.task import PrioritySource, TaskPriority
from app.services.priority_classifier import PriorityResult


class FakeClassifier:
    def __init__(self) -> None:
        self.result = PriorityResult(TaskPriority.ALTA, PrioritySource.JEV)
        self.calls: list[tuple[str, str | None]] = []

    def classify(self, title: str, description: str | None) -> PriorityResult:
        self.calls.append((title, description))
        return self.result


def _client(factory: sessionmaker[Session], classifier: FakeClassifier) -> TestClient:
    def override_db() -> Iterator[Session]:
        session = factory()
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    api = create_app()
    api.dependency_overrides[get_db] = override_db
    api.dependency_overrides[get_classifier] = lambda: classifier
    return TestClient(api, raise_server_exceptions=False)


@pytest.fixture
def classifier() -> FakeClassifier:
    return FakeClassifier()


@pytest.fixture
def client(tmp_path: Path, classifier: FakeClassifier) -> Iterator[TestClient]:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'api.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    yield _client(build_session_factory(engine), classifier)
    engine.dispose()


@pytest.fixture
def client_banco_quebrado(tmp_path: Path, classifier: FakeClassifier) -> Iterator[TestClient]:
    caminho = tmp_path / "pasta-inexistente" / "api.db"
    engine = create_engine(f"sqlite:///{caminho}", connect_args={"check_same_thread": False})
    yield _client(build_session_factory(engine), classifier)
    engine.dispose()
```

- [ ] **Step 2: Escrever os testes que falham** — `tests/integration/test_tasks_api.py`

```python
import json

import pytest
from fastapi.testclient import TestClient

from app.schemas.task import PRIORITY_FALLBACK_NOTICE, PrioritySource, TaskPriority
from app.services.priority_classifier import PriorityResult


def criar(client: TestClient, **corpo: str) -> dict:
    resposta = client.post("/tasks", json={"title": "Tarefa", **corpo})
    assert resposta.status_code == 201
    return resposta.json()


def test_ciclo_completo(client: TestClient, classifier) -> None:
    tarefa = criar(client, title="Escrever relatório", description="rascunho")
    assert tarefa["status"] == "pendente"
    assert tarefa["priority"] == "alta"
    assert tarefa["priority_source"] == "jev"
    assert tarefa["priority_notice"] is None
    assert classifier.calls == [("Escrever relatório", "rascunho")]
    tarefa_id = tarefa["id"]

    assert client.get(f"/tasks/{tarefa_id}").json() == tarefa
    assert [t["id"] for t in client.get("/tasks").json()] == [tarefa_id]

    editada = client.patch(f"/tasks/{tarefa_id}", json={"priority": "baixa"}).json()
    assert editada["priority"] == "baixa"
    assert editada["priority_source"] == "manual"

    concluida = client.patch(f"/tasks/{tarefa_id}/complete").json()
    assert concluida["status"] == "concluida"
    assert client.get("/tasks", params={"status": "pendente"}).json() == []
    assert len(client.get("/tasks", params={"status": "concluida"}).json()) == 1

    assert client.delete(f"/tasks/{tarefa_id}").status_code == 204
    assert client.get(f"/tasks/{tarefa_id}").status_code == 404
    assert client.get("/tasks").json() == []


def test_lista_vem_ordenada_por_id(client: TestClient) -> None:
    ids = [criar(client, title=f"t{i}")["id"] for i in range(3)]
    assert [t["id"] for t in client.get("/tasks").json()] == ids


def test_fallback_devolve_aviso_amigavel(client: TestClient, classifier) -> None:
    classifier.result = PriorityResult(TaskPriority.MEDIA, PrioritySource.FALLBACK)
    tarefa = criar(client)
    assert tarefa["priority_source"] == "fallback"
    assert tarefa["priority_notice"] == PRIORITY_FALLBACK_NOTICE


def test_prioridade_manual_nao_e_sobrescrita_ao_editar_o_titulo(
    client: TestClient, classifier
) -> None:
    tarefa_id = criar(client)["id"]
    client.patch(f"/tasks/{tarefa_id}", json={"priority": "baixa"})
    editada = client.patch(f"/tasks/{tarefa_id}", json={"title": "Outro título"}).json()
    assert editada["title"] == "Outro título"
    assert editada["priority"] == "baixa"
    assert editada["priority_source"] == "manual"
    assert len(classifier.calls) == 1


def test_editar_prioridade_para_o_mesmo_valor_marca_manual(client: TestClient) -> None:
    tarefa_id = criar(client)["id"]
    editada = client.patch(f"/tasks/{tarefa_id}", json={"priority": "alta"}).json()
    assert editada["priority_source"] == "manual"


def test_concluir_duas_vezes_nao_gera_erro(client: TestClient) -> None:
    tarefa_id = criar(client)["id"]
    assert client.patch(f"/tasks/{tarefa_id}/complete").status_code == 200
    assert client.patch(f"/tasks/{tarefa_id}/complete").status_code == 200


def test_remover_duas_vezes_devolve_404_na_segunda(client: TestClient) -> None:
    tarefa_id = criar(client)["id"]
    assert client.delete(f"/tasks/{tarefa_id}").status_code == 204
    assert client.delete(f"/tasks/{tarefa_id}").status_code == 404


@pytest.mark.parametrize(
    ("metodo", "url", "corpo"),
    [
        ("get", "/tasks/999", None),
        ("patch", "/tasks/999", {"title": "x"}),
        ("patch", "/tasks/999/complete", None),
        ("delete", "/tasks/999", None),
    ],
)
def test_id_inexistente_devolve_404_amigavel(
    client: TestClient, metodo: str, url: str, corpo: dict | None
) -> None:
    resposta = getattr(client, metodo)(url, **({"json": corpo} if corpo else {}))
    assert resposta.status_code == 404
    erro = resposta.json()["erro"]
    assert erro["codigo"] == "TAREFA_NAO_ENCONTRADA"
    assert erro["mensagem"] == "Não encontramos essa tarefa. Ela pode ter sido removida."


@pytest.mark.parametrize(
    ("metodo", "url", "corpo", "trecho"),
    [
        ("post", "/tasks", {}, "O título é obrigatório."),
        ("post", "/tasks", {"title": "   "}, "não pode ficar em branco"),
        ("post", "/tasks", {"title": "x", "priority": "alta"}, "não pode ser enviado"),
        ("patch", "/tasks/1", {"priority": "urgentissima"}, "Prioridade inválida"),
        ("patch", "/tasks/1", {"priority": None}, "Informe ao menos um campo"),
        ("patch", "/tasks/1", {"description": "a" * 501}, "500"),
        ("patch", "/tasks/1", {}, "Informe ao menos um campo"),
    ],
)
def test_corpo_invalido_devolve_422_amigavel(
    client: TestClient, metodo: str, url: str, corpo: dict, trecho: str
) -> None:
    resposta = getattr(client, metodo)(url, json=corpo)
    assert resposta.status_code == 422
    assert resposta.json()["erro"]["codigo"] == "DADOS_INVALIDOS"
    assert trecho in json.dumps(resposta.json(), ensure_ascii=False)


def test_json_malformado_devolve_422_amigavel(client: TestClient) -> None:
    resposta = client.post(
        "/tasks", content=b'{"title": ', headers={"content-type": "application/json"}
    )
    assert resposta.status_code == 422
    assert resposta.json()["erro"]["codigo"] == "DADOS_INVALIDOS"


def test_status_na_query_com_maiusculas_lista_as_opcoes(client: TestClient) -> None:
    resposta = client.get("/tasks", params={"status": "Pendente"})
    assert resposta.status_code == 422
    assert "Status inválido. Use: pendente ou concluida." in resposta.text


@pytest.mark.parametrize("task_id", ["abc", "0", "-5", "99999999999999999999"])
def test_id_invalido_nunca_gera_500(client: TestClient, task_id: str) -> None:
    for metodo in ("get", "delete"):
        resposta = getattr(client, metodo)(f"/tasks/{task_id}")
        assert resposta.status_code == 422
        assert resposta.json()["erro"]["codigo"] == "DADOS_INVALIDOS"


def test_falha_do_banco_devolve_503_sem_vazar_detalhes(
    client_banco_quebrado: TestClient,
) -> None:
    resposta = client_banco_quebrado.get("/tasks")
    assert resposta.status_code == 503
    erro = resposta.json()["erro"]
    assert erro["codigo"] == "BANCO_INDISPONIVEL"
    assert "pasta-inexistente" not in resposta.text
    assert "sqlite" not in resposta.text.lower()
    assert client_banco_quebrado.get("/tasks").status_code == 503


def test_documentacao_openapi_esta_disponivel(client: TestClient) -> None:
    assert client.get("/docs").status_code == 200
    esquema = client.get("/openapi.json").json()
    assert set(esquema["paths"]) == {"/tasks", "/tasks/{task_id}", "/tasks/{task_id}/complete"}
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `.venv/bin/pytest tests/integration/test_tasks_api.py -v`
Expected: FAIL com `ModuleNotFoundError: app.main`.

- [ ] **Step 4: Implementar** — `app/main.py`

```python
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
```

- [ ] **Step 5: Rodar tudo e ver passar**

```bash
.venv/bin/pytest --cov=app --cov-report=term-missing -q
.venv/bin/ruff check app tests && .venv/bin/ruff format --check app tests && .venv/bin/mypy app
```
Expected: todos os testes passam (ciclo 1, unitários e integração), cobertura total >= 90%, ferramentas limpas. Se algum teste de erro falhar por detalhe da mensagem, inspecione `resposta.json()` e ajuste o código em `app/`, nunca o texto esperado do spec.

- [ ] **Step 6: Commit**

```bash
git add app/main.py tests/integration/conftest.py tests/integration/test_tasks_api.py
git commit -m "feat: adiciona main.py e testes de integração da API" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Documentação e verificação ponta a ponta

**Files:**
- Modify: `README.md`
- Modify: `docs/decisoes-tecnicas.md`

**Interfaces:**
- Consumes: a API completa (Tasks 1 a 7) e os resultados reais da suíte.

- [ ] **Step 1: Verificar a API de verdade** (guarde as saídas; elas viram evidência no relatório)

```bash
rm -f tasks.db
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --port 8765 &
sleep 3
curl -s -o /dev/null -w "docs: %{http_code}\n" http://127.0.0.1:8765/docs
curl -s -X POST http://127.0.0.1:8765/tasks -H 'content-type: application/json' -d '{"title":"Corrigir bug urgente em produção"}'
curl -s http://127.0.0.1:8765/tasks
curl -s -X PATCH http://127.0.0.1:8765/tasks/1 -H 'content-type: application/json' -d '{"priority":"baixa"}'
curl -s -X PATCH http://127.0.0.1:8765/tasks/1/complete
curl -s "http://127.0.0.1:8765/tasks?status=concluida"
curl -s -X POST http://127.0.0.1:8765/tasks -H 'content-type: application/json' -d '{}'
curl -s http://127.0.0.1:8765/tasks/999
curl -s -o /dev/null -w "delete: %{http_code}\n" -X DELETE http://127.0.0.1:8765/tasks/1
kill %1
rm -f tasks.db
```
Expected: `docs: 200`; criação com `priority_source` `fallback` ou `jev`; edição com `manual`; erros 422 e 404 no formato `{"erro": {...}}`; `delete: 204`. Sem chave de API configurada a prioridade vem do fallback (`alta`, por causa de "urgente"). **Não** use a chave do `.env` nesta tarefa (o worktree nem a possui): a chamada real ao Jev foi autorizada pelo usuário e é feita pelo arquiteto, na `main`, depois da orquestração. Resultado do teste com o código do ciclo 1: HTTP 401 `User not found` nos dois endpoints (`/v1/systemone` e `/alpha/decisions`), ou seja, a chave não foi aceita pelo OpenRouter; o fallback funcionou (`alta`, `source=fallback`).

- [ ] **Step 2: Rodar a suíte para obter os números reais**

```bash
.venv/bin/pytest --cov=app -q
```
Anote a quantidade de testes passando e a cobertura total; substitua `<N>` e `<X>` no README abaixo por esses valores.

- [ ] **Step 3: Atualizar `README.md`** — substitua o arquivo inteiro por este texto (mantenha as 5 seções com os títulos exatos, na ordem, e os campos `[preencher]` literais)

````markdown
# UFG_todo

Micro-API de tarefas para equipes, com prioridade sugerida automaticamente.

## O que o projeto resolve?

Equipes precisam registrar e acompanhar tarefas de forma simples, sem uma ferramenta pesada. A prioridade é sugerida automaticamente para reduzir o trabalho manual, e a pessoa pode ajustá-la depois. O público é o uso interno de uma equipe.

Funcionalidades do MVP:
- criar, listar, detalhar, editar e remover tarefas;
- marcar como concluída e filtrar por status;
- prioridade automática (Jev, com fallback local) e edição manual da prioridade;
- mensagens de erro amigáveis, em português.

## Como instalar e executar?

Pré-requisito: Python 3.12.

1. Crie o ambiente virtual: `python3.12 -m venv .venv`
2. Ative-o: `source .venv/bin/activate`
3. Instale as dependências: `pip install -r requirements-dev.txt`
4. Copie as variáveis de ambiente: `cp .env.example .env`
5. Crie o banco: `alembic upgrade head`
6. Suba a API: `uvicorn app.main:app`

A documentação interativa fica em `http://127.0.0.1:8000/docs`.

| Variável | Obrigatória? | Padrão | Para que serve |
|---|---|---|---|
| `OPENROUTER_API_KEY` | não | (vazia) | chave do OpenRouter para o Jev |
| `OPENROUTER_BASE_URL` | não | `https://openrouter.ai/api` | endereço base do OpenRouter |
| `JEV_MODEL` | não | `typesafe/jev-1.13` | modelo do Jev (versão fixa) |
| `CLASSIFIER_TIMEOUT_SECONDS` | não | `5.0` | tempo máximo de espera pelo Jev |
| `CLASSIFIER_MAX_RETRIES` | não | `1` | novas tentativas em falha temporária |
| `JEV_MIN_CONFIDENCE` | não | `0.5` | confiança mínima aceita do Jev |
| `DATABASE_URL` | não | `sqlite:///./tasks.db` | endereço do banco SQLite |

Sem `OPENROUTER_API_KEY`, a API continua funcionando e a prioridade usa o fallback local.

Endpoints:

| Método e rota | Função |
|---|---|
| `POST /tasks` | criar tarefa |
| `GET /tasks?status=pendente` | listar, com filtro opcional por status (`pendente` ou `concluida`) |
| `GET /tasks/{id}` | detalhar |
| `PATCH /tasks/{id}` | editar campos e prioridade |
| `PATCH /tasks/{id}/complete` | marcar como concluída |
| `DELETE /tasks/{id}` | remover |

## Como rodar os testes?

```bash
pytest
pytest --cov=app
ruff check app tests
mypy app
```

Os testes não usam rede nem precisam de chave de API. Resultado da última execução: <N> testes passando, cobertura total de <X>%.

## Quais limites existem?

- **Escopo do MVP:** sem autenticação, sem multiusuário, sem cache nem filas.
- **SQLite:** arquivo local, adequado a uma equipe pequena, sem concorrência alta nem alta disponibilidade.
- **Listagem:** sem paginação.
- **Prioridade automática:** depende de um serviço externo (Jev/OpenRouter). Em falha, usa uma heurística simples por palavras-chave, menos precisa. A pessoa é avisada (`priority_notice`) e pode corrigir.
- **Privacidade:** título e descrição das tarefas são enviados ao OpenRouter/TypeSafe para classificar. Sem chave, nada é enviado.
- **Recalculo:** a prioridade não é recalculada quando título ou descrição são editados.
- **Descrição:** não é possível apagá-la por `PATCH`; só substituí-la.
- **Validações:** título de 1 a 100 caracteres e descrição de até 500.
- **Idioma:** mensagens apenas em português do Brasil.
- **Endpoint do Jev:** a documentação do OpenRouter diverge sobre o endpoint (`/v1/systemone` ou `/alpha/decisions`); ele ainda precisa ser validado com uma chave real.
- **Frontend:** ainda não existe.

## Como a IA foi usada no processo?

**IA no produto (em tempo de execução):** o Jev classifica a prioridade na criação da tarefa, via OpenRouter, com fallback local. Usamos o Jev, e não um LLM de chat, porque ele é um modelo de decisão estruturada, que devolve respostas tipadas com probabilidades.

**IA no desenvolvimento:** o agente de codificação gerou as dependências, a configuração das ferramentas, os schemas, o tratamento de erros, o classificador, o model, o repository, o service, as rotas, os testes, os diagramas, as decisões técnicas, o CI e este README. O fluxo foi: contexto e escopo definidos em prompt, geração, verificação automática (testes, `ruff`, `mypy`, `pip check`) e relatório de evidências para revisão humana.

- Ferramenta/modelo do agente: [preencher]
- Revisão humana feita por: [preencher]

O código gerado por IA foi revisado e validado por testes. As decisões de escopo e as regras de negócio vieram de pessoas.

## Arquitetura

Veja os diagramas e o modelo de dados em [docs/arquitetura.md](docs/arquitetura.md) e as decisões em [docs/decisoes-tecnicas.md](docs/decisoes-tecnicas.md).
````

- [ ] **Step 4: Acrescentar ADRs** — ao final de `docs/decisoes-tecnicas.md`

```markdown

## 11. Sessão síncrona e rotas `def`
- **Contexto:** o classificador usa `httpx.Client` síncrono e o SQLite não se beneficia de I/O assíncrono.
- **Decisão:** SQLAlchemy síncrono, uma sessão por requisição (`get_db`, com rollback em falha) e rotas declaradas com `def`, que o FastAPI executa em threadpool.
- **Motivo:** menos complexidade e nenhuma chamada bloqueante no loop de eventos.

## 12. Esquema do banco por migração
- **Decisão:** Alembic com a migração `0001`; produção usa `alembic upgrade head`. Os testes criam as tabelas com `Base.metadata.create_all`.
- **Motivo:** evolução do esquema rastreável, sem criar tabelas implicitamente ao subir a API.

## 13. Repository atrás de um `Protocol`
- **Decisão:** o service depende de `TaskRepositoryPort`, e `TaskRepository` o implementa.
- **Motivo:** o service é testado com um repository em memória, sem banco. Os métodos de listagem se chamam `list_tasks` para não sombrear o `list` embutido.

## 14. Regras do `PATCH` e de concluir
- **Decisão:** só campos informados e não nulos são aplicados; por isso a descrição não pode ser apagada. Editar a prioridade grava `manual` (mesmo com o valor igual) e não chama o classificador. Concluir uma tarefa já concluída responde 200.
- **Motivo:** regra simples e previsível; reclassificação ao editar título ou descrição fica como pendência.

## 15. `id` limitado ao intervalo do SQLite
- **Decisão:** `id` na rota exige inteiro entre 1 e 9223372036854775807.
- **Motivo:** um inteiro maior que o suportado pelo SQLite gerava erro interno (500); agora gera 422 amigável.
```

- [ ] **Step 5: Validar a documentação**

```bash
grep -n '^## ' README.md
grep -c '\[preencher\]' README.md
grep -n -i "em construção" README.md || echo "sem 'em construção'"
grep -n '<N>\|<X>' README.md || echo "números substituídos"
test -f docs/arquitetura.md && test -f docs/decisoes-tecnicas.md && echo "links ok"
grep -c '^## 1[1-5]\.' docs/decisoes-tecnicas.md
```
Expected: 5 seções na ordem, depois `## Arquitetura`; `2`; `sem 'em construção'`; `números substituídos`; `links ok`; `5`.

- [ ] **Step 6: Commit**

```bash
git add README.md docs/decisoes-tecnicas.md
git commit -m "docs: atualiza README e decisões técnicas com a API completa" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

## Relatório final (feito pelo arquiteto, não é tarefa de worker)

Reunir, com saídas literais: versão do Python e `pip check`; `alembic upgrade head` em banco temporário; `pytest --cov=app`; `ruff check`, `ruff format --check` e `mypy`; os JSONs reais dos 6 endpoints e dos erros 404, 422 e 503; abertura de `/docs`; validação do README (5 seções, `[preencher]`, links, sem `<N>`/`<X>`); **Pendências** (chamada real ao Jev dependente de autorização, endpoint `/v1/systemone` a validar, reclassificação ao editar título ou descrição, apagar descrição por `PATCH`, aviso de depreciação `httpx`/`httpx2`, `black` indisponível no Python 3.12.5); **Estabilidade** (sem lockfile, `.python-version` 3.12 genérico); **Riscos** (Jev externo e divergência de endpoint, SQLite sem concorrência alta, textos de tarefas enviados a terceiros); **Diagramas** (conferir se `docs/arquitetura.md` ainda bate com a implementação).
