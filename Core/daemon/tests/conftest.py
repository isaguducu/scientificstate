"""Shared test fixtures for daemon routes."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

# Ensure src is importable from any working directory
sys.path.insert(0, str(Path(__file__).parents[1]))


@pytest.fixture()
async def client():
    """Return an AsyncClient backed by the FastAPI app with a fresh in-memory DB."""
    # Patch DB path to an in-memory-style temp file for test isolation
    import tempfile

    import src.storage.schema as schema_mod

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    original_db = schema_mod._DB_PATH
    schema_mod._DB_PATH = Path(tmp.name)

    from src.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        # Trigger lifespan startup so DB tables are created
        async with app.router.lifespan_context(app):
            yield ac

    schema_mod._DB_PATH = original_db
    Path(tmp.name).unlink(missing_ok=True)
