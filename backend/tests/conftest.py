"""Shared fixtures.

Two kinds of database are used:
  - `db`: an empty in-memory database the unit tests build tiny, hand-made
    scenarios in, so each failure state is tested in isolation and the
    expected number can be worked out by hand.
  - `client`: the full seeded dataset (data-gen/generate_data.py) in a
    throwaway file, driven through the real HTTP API -- this is what checks
    RBAC and the resolve workflow end to end.

CONTROLFORGE_DB has to be set before anything imports app.database, which is
why it happens at module import time here rather than inside a fixture.
"""

import os
import sys
import tempfile

_TMP_DIR = tempfile.mkdtemp(prefix="controlforge-test-")
os.environ["CONTROLFORGE_DB"] = os.path.join(_TMP_DIR, "test.sqlite3")
os.environ.setdefault("CONTROLFORGE_SECRET", "test-secret-not-for-real-use-padding-to-32b+")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))
sys.path.insert(0, os.path.join(ROOT, "data-gen"))

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.database import Base  # noqa: E402

DEMO_PASSWORD = "controlforge-demo-2026"


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="session")
def seeded():
    import contextlib
    import io
    import generate_data
    with contextlib.redirect_stdout(io.StringIO()):
        generate_data.main(seed=42)
    return True


@pytest.fixture
def client(seeded):
    """Read-only tests share the session-wide seed. Tests that write (resolve
    issues) also request `fresh_seed` so they can't leak state."""
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


@pytest.fixture
def fresh_seed():
    """For tests that write (resolve issues): reseed before AND after so the
    order tests run in never matters."""
    import contextlib
    import io
    import generate_data
    with contextlib.redirect_stdout(io.StringIO()):
        generate_data.main(seed=42)
    yield
    with contextlib.redirect_stdout(io.StringIO()):
        generate_data.main(seed=42)


_token_cache = {}


@pytest.fixture
def login(client):
    def _login(username: str) -> dict:
        if username not in _token_cache:
            r = client.post("/api/auth/login", json={"identifier": username, "password": DEMO_PASSWORD})
            assert r.status_code == 200, r.text
            _token_cache[username] = r.json()["token"]
        return {"Authorization": f"Bearer {_token_cache[username]}"}
    return _login
