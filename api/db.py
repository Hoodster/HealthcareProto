from __future__ import annotations

from typing import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from api.config import get_database_connection_url


class Base(DeclarativeBase):
    pass


def _create_engine():
    url = get_database_connection_url()
    connect_args = {}
    if url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    return create_engine(url, future=True, echo=False, connect_args=connect_args)


engine = _create_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db() -> None:
    from api.models import APP_SCHEMA_NAME

    if engine.dialect.name == "postgresql":
        with engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{APP_SCHEMA_NAME}"'))

    app_tables = [
        table
        for table in Base.metadata.tables.values()
        if table.schema in (None, APP_SCHEMA_NAME)
    ]
    Base.metadata.create_all(bind=engine, tables=app_tables)


def get_db_session() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
