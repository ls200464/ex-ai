"""Regression tests for the application's default configuration.

The default ``DATABASE_URL`` is ``sqlite+aiosqlite``, so the async engine can only
be constructed when the ``aiosqlite`` driver is installed. It was missing from
both ``requirements.txt`` and ``pyproject.toml``, which meant the documented quick
start (uvicorn with default settings) crashed while importing ``app.database``.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings


def test_default_database_url_targets_sqlite():
    assert settings.DATABASE_URL.startswith("sqlite+aiosqlite"), (
        "the default DATABASE_URL should target the bundled SQLite driver, so a "
        "fresh checkout runs without external services"
    )


def test_default_settings_build_an_async_engine():
    """Creating the engine loads the driver, so a missing driver fails here."""
    engine = create_async_engine(settings.DATABASE_URL)
    assert engine.dialect.driver == "aiosqlite"


def test_app_database_module_imports():
    """``app.database`` builds an engine at import time, so importing it proves
    the default configuration is usable end to end."""
    import app.database

    assert app.database.engine is not None
