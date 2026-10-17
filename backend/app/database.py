from collections.abc import Generator

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base
from app.settings import settings


def build_engine(database_url: str | None = None) -> Engine:
    url = database_url or settings.database_url
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args, pool_pre_ping=True)

    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def enable_sqlite_foreign_keys(dbapi_connection: object, _connection_record: object) -> None:
            cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


engine = build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables and apply small additive compatibility migrations for the MVP."""
    Base.metadata.create_all(bind=engine)

    # create_all does not add columns to an existing table. Keep databases created
    # before source-content storage usable without dropping collected research runs.
    inspector = inspect(engine)
    if "sources" in inspector.get_table_names():
        source_columns = {column["name"] for column in inspector.get_columns("sources")}
        if "content_text" not in source_columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE sources ADD COLUMN content_text TEXT"))
