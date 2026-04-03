import os
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "mysql+pymysql://app:apppass@localhost:3307/transfers_test",
)


@pytest.fixture(scope="session")
def engine():
    return create_engine(TEST_DB_URL, pool_pre_ping=True)


@pytest.fixture(scope="session")
def _run_migrations(engine):
    """Run Alembic migrations against the test database once per session."""
    from alembic.config import Config
    from alembic import command

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", TEST_DB_URL)
    os.environ["DATABASE_URL"] = TEST_DB_URL

    # Ensure the app config points to the test DB (for background tasks etc.)
    from app.config import settings
    settings.database_url = TEST_DB_URL

    # Drop everything first to ensure a clean slate, then run migrations.
    from app.database import Base
    from app.models import Vehicle, Transfer, TransferStatusHistory, Notification  # noqa: F401
    Base.metadata.drop_all(engine)

    # Reset alembic version tracking
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
        conn.commit()

    command.upgrade(cfg, "head")
    yield


@pytest.fixture()
def clean_db(engine, _run_migrations):
    """Truncate all tables before a test. Returns the engine."""
    with engine.connect() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        for table in ("notifications", "transfer_status_history", "transfers", "vehicles"):
            conn.execute(text(f"TRUNCATE TABLE {table}"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
        conn.commit()
    return engine


@pytest.fixture()
def client(clean_db):
    """Starlette TestClient wired to the test database."""
    from starlette.testclient import TestClient
    from app.main import app
    from app.database import get_db

    TestSession = sessionmaker(bind=clean_db)

    def override_get_db():
        session = TestSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
