"""Shared test fixtures.

Tests run against a real, throwaway Postgres named by TEST_DATABASE_URL. The
database name must end in "_test" so the suite can never be pointed at the
live database by accident: every test truncates every table.
"""

import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")
if not TEST_DATABASE_URL.rsplit("/", 1)[-1].endswith("_test"):
    raise pytest.UsageError(
        "Set TEST_DATABASE_URL to a throwaway Postgres whose database name ends in _test "
        "(see scripts/test.sh). Refusing to run against anything else."
    )

# Settings and the SQLAlchemy engine are built at import time, so the
# environment must be in place before anything under app/ is imported.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault("CHECKIN_TOKEN_SECRET", "test-secret")
os.environ.setdefault("APP_ENV", "test")

BACKEND_DIR = Path(__file__).resolve().parents[1]

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.db import Base, engine  # noqa: E402
from app.core.rate_limit import RateLimiter  # noqa: E402
from app.main import app  # noqa: E402

PASSWORD = "correct horse battery"


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        check=True,
        env={**os.environ, "DATABASE_URL": TEST_DATABASE_URL},
    )


@pytest.fixture(autouse=True)
def clean_state() -> Iterator[None]:
    yield
    tables = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} CASCADE"))
    for limiter in RateLimiter.instances:
        limiter.reset()


def make_client() -> TestClient:
    # Not used as a context manager, so the app lifespan (and with it the
    # background alert loop) never starts during tests.
    return TestClient(app)


@pytest.fixture
def client() -> TestClient:
    return make_client()


def register(client: TestClient, username: str, password: str = PASSWORD) -> list[str]:
    response = client.post("/api/auth/register", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["recovery_codes"]


def login(client: TestClient, username: str, password: str = PASSWORD):
    return client.post("/api/auth/login", json={"username": username, "password": password})


def register_and_login(username: str) -> TestClient:
    """Returns a fresh client holding a logged-in session for a new account."""
    client = make_client()
    register(client, username)
    assert login(client, username).status_code == 200
    return client
