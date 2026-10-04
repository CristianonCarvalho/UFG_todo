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
        session.add(
            Task(title="t", priority=TaskPriority.MEDIA, priority_source=PrioritySource.JEV)
        )
        session.commit()
        assert session.query(Task).one().status is TaskStatus.PENDENTE

    command.downgrade(cfg, "base")
    assert "tasks" not in inspect(engine).get_table_names()
    engine.dispose()
