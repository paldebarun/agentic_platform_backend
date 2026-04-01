"""
Agno database configuration for session and chat history persistence.

Uses the same PostgreSQL connection settings as postgres_client (DATABASE_URL
or POSTGRES_* env vars). Provides a PostgresDb instance for Agno's built-in
session/chat history persistence.
"""

import os
from typing import Optional, Any

from services.db_service import _get_db_connection_string

_agno_db: Optional[Any] = None
_SESSION_TABLE = "agno_sessions"
_table_extend_existing_patched = False


def _apply_sqlalchemy_extend_existing_patch():
    """
    Ensure SQLAlchemy Table uses extend_existing=True so Agno's PostgresDb
    does not raise when the same table is registered multiple times in MetaData
    (e.g. 'Table ai.agno_sessions is already defined for this MetaData instance').
    """
    global _table_extend_existing_patched
    if _table_extend_existing_patched:
        return
    try:
        from sqlalchemy.schema import Table
        _orig_init = Table.__init__

        def _patched_init(self, *args, **kwargs):
            kwargs.setdefault("extend_existing", True)
            return _orig_init(self, *args, **kwargs)

        Table.__init__ = _patched_init
        _table_extend_existing_patched = True
        print("Applied SQLAlchemy Table extend_existing patch for Agno PostgresDb")
    except Exception as e:
        print("Could not apply extend_existing patch: %s", e)


def _get_agno_db_url() -> Optional[str]:
    """
    Build Agno/SQLAlchemy PostgreSQL URL from the same config as postgres_client.
    Converts postgresql:// to postgresql+psycopg2:// for SQLAlchemy engine.
    """
    raw = _get_db_connection_string()
    if not raw or not raw.strip():
        return None
    raw = raw.strip()
    if raw.startswith("postgresql://"):
        return "postgresql+psycopg2://" + raw[len("postgresql://") :]
    if raw.startswith("postgresql+psycopg2://") or raw.startswith("postgresql+psycopg://"):
        return raw
    if raw.startswith("postgres://"):
        return "postgresql+psycopg2://" + raw[len("postgres://") :]
    return "postgresql+psycopg2://" + raw


def get_agno_db():
    """
    Return a shared Agno PostgresDb instance for session/chat history persistence,
    or None if PostgreSQL is not configured or Agno's PostgresDb is unavailable.

    Uses the same connection parameters as postgres_client (DATABASE_URL or
    POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD).
    """
    global _agno_db
    if _agno_db is not None:
        return _agno_db

    db_url = _get_agno_db_url()
    if not db_url:
        print("No PostgreSQL URL configured; Agno session persistence disabled")
        return None

    _apply_sqlalchemy_extend_existing_patch()

    try:
        from agno.db.postgres import PostgresDb
    except ImportError as e:
        print(
            "Agno PostgresDb not available (%s); session persistence disabled", e
        )
        return None

    try:
        _agno_db = PostgresDb(
            db_url=db_url,
            session_table=_SESSION_TABLE,
        )
        print(
            "Agno PostgresDb initialized for session persistence (table=%s)",
            _SESSION_TABLE,
        )
        return _agno_db
    except Exception as e:
        print(
            "Failed to initialize Agno PostgresDb (%s); session persistence disabled",
            e,
        )
        return None
