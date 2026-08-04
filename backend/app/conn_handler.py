# Import future annotations for Pydantic models
from __future__ import annotations
from typing import Optional

# Import general python packages
import os

# Import sqlite3 for database connection
import sqlite3

# Import schema_validator for default database path
from .schema_validator import _DEFAULT_SCHEMA_FILE, _DEFAULT_SQLITE_FILE

# Function to open a SQLite connection from a handler
def init_connection() -> sqlite3.Connection:
    """Open and return a sqlite3 connection to the default database.

    Returns
    -------
    sqlite3.Connection
        An open connection with autocommit-style isolation level (check_same_thread=False).
    """
    try:
        # (Re)initialize with schema.sql if the file is missing or exists but has no
        # tables yet (e.g. an empty stub file left by a bind mount) — schema.sql uses
        # DROP TABLE IF EXISTS, so it must never run against a DB that already has tables.
        needs_init = not os.path.exists(_DEFAULT_SQLITE_FILE)
        if not needs_init:
            conn = sqlite3.connect(_DEFAULT_SQLITE_FILE)
            table_count = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
            conn.close()
            needs_init = table_count == 0
        if needs_init:
            with open(_DEFAULT_SCHEMA_FILE, "r") as f:
                schema_sql = f.read()
            conn = sqlite3.connect(_DEFAULT_SQLITE_FILE)
            conn.executescript(schema_sql)
            conn.commit()
            conn.close()
            os.chmod(_DEFAULT_SQLITE_FILE, 0o664)
        # Open the connection with check_same_thread=False to allow usage across threads
        connection = sqlite3.connect(_DEFAULT_SQLITE_FILE, check_same_thread=False)
        connection.row_factory = sqlite3.Row   # column-name access on cursors
        connection.execute("PRAGMA foreign_keys = ON;")
        return connection
    except sqlite3.Error as err:
        raise Exception(f"SQLite Connection Error: {err}") from err

        
