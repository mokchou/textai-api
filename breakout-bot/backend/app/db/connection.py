"""Connexion SQLite (WAL) et initialisation du schéma."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

SCHEMA_PATH = Path(__file__).parent / "schema.sql"
_local = threading.local()
_db_path: Path | None = None


def init_db(path: Path) -> None:
    global _db_path
    _db_path = path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA_PATH.read_text())
    conn.commit()
    conn.close()


def get_conn() -> sqlite3.Connection:
    """Une connexion par thread (FastAPI threadpool + runners)."""
    assert _db_path is not None, "init_db() doit être appelé au démarrage"
    conn = getattr(_local, "conn", None)
    if conn is None or getattr(_local, "path", None) != _db_path:
        conn = sqlite3.connect(_db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _local.conn = conn
        _local.path = _db_path
    return conn
