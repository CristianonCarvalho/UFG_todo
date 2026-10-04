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
