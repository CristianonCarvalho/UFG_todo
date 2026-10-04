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
