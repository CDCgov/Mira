# Import future annotations for Pydantic models
from __future__ import annotations
from typing import Optional

# Import general python packages
import os
import re
import threading

# Import sqlite3 for database connection
import sqlite3

# Import schema_validator for default database path
from .schema_validator import _DEFAULT_SQLITE_PATH, _ensure_storage_directory

# Define storage paths for sqlite database and schema file
_DEFAULT_MIRA_SCHEMA_FILE = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "sqlite/mira_schema.sql"))
_DEFAULT_SEQSENDER_SCHEMA_FILE = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "sqlite/seqsender_schema.sql"))

# Create sqlite database if it doesn't exist, using schema.sql
_DEFAULT_SQLITE_FILE = os.path.join(_DEFAULT_SQLITE_PATH, "mira.db")

# Guards first-time schema init against concurrent requests racing in via asyncio.to_thread
_init_lock = threading.Lock()

# Regular expression pattern to match CREATE TABLE statements in SQL schema files
_CREATE_TABLE_PATTERN = re.compile(
    r'^\s*CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?'
    r'(?:(?:"([^"]+)")|(?:`([^`]+)`)|(?:\[([^\]]+)\])|([^\s(]+))',
    re.IGNORECASE,
)

# Function to ensure that all tables declared in the schema files exist in the database
def _ensure_schema_tables(connection: sqlite3.Connection, schema_files: tuple[str, ...]) -> None:
    """Create tables declared by the schema files when they do not already exist."""
    existing_tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    }
    # Iterate over each schema file and create any missing tables
    for schema_file in schema_files:
        with open(schema_file, "r") as file:
            statement_lines: list[str] = []
            for line in file:
                statement_lines.append(line)
                statement = "".join(statement_lines)
                if not sqlite3.complete_statement(statement):
                    continue
                match = _CREATE_TABLE_PATTERN.match(statement)
                if match:
                    table_name = next(group for group in match.groups() if group is not None)
                    if table_name not in existing_tables:
                        connection.execute(statement)
                        existing_tables.add(table_name)
                statement_lines.clear()
    # Commit any changes made to the database
    connection.commit()

# Function to open a SQLite connection from a handler
def init_connection() -> sqlite3.Connection:
    """
    Open and return a sqlite3 connection to the default database.
    Returns
    -------
    sqlite3.Connection
        An open connection with autocommit-style isolation level (check_same_thread=False).
    """
    try:
        with _init_lock:
            # Recreate the storage directory if the host removed/moved it out from under us,
            # otherwise sqlite3.connect() below fails with "unable to open database file"
            _ensure_storage_directory(_DEFAULT_SQLITE_PATH)
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
                # Initiate database with mira_schema.sql and seqsender_schema.sql
                with open(_DEFAULT_MIRA_SCHEMA_FILE, "r") as f:
                    mira_schema_sql = f.read()
                with open(_DEFAULT_SEQSENDER_SCHEMA_FILE, "r") as f:
                    seqsender_schema_sql = f.read()
                conn = sqlite3.connect(_DEFAULT_SQLITE_FILE)
                conn.executescript(mira_schema_sql)
                conn.executescript(seqsender_schema_sql)
                conn.commit()
                conn.close()
                os.chmod(_DEFAULT_SQLITE_FILE, 0o664)
            # Restore any individual tables that are missing from an existing database.
            conn = sqlite3.connect(_DEFAULT_SQLITE_FILE)
            try:
                _ensure_schema_tables(
                    connection = conn,
                    schema_files = (_DEFAULT_SEQSENDER_SCHEMA_FILE, _DEFAULT_MIRA_SCHEMA_FILE),
                )
            finally:
                conn.close()
        # Open the connection with check_same_thread=False to allow usage across threads
        connection = sqlite3.connect(_DEFAULT_SQLITE_FILE, check_same_thread=False)
        connection.row_factory = sqlite3.Row   # column-name access on cursors
        connection.execute("PRAGMA foreign_keys = ON;")
        # Lightweight, idempotent migrations for columns added after a DB was first created
        _apply_migrations(connection)
        return connection
    except sqlite3.Error as err:
        raise Exception(f"SQLite Connection Error: {err}") from err

# Apply lightweight, idempotent schema migrations to an existing database so that
# columns added to schema.sql after a DB was first created are backfilled in place.
def _apply_migrations(connection: sqlite3.Connection) -> None:
    """Add newer columns to pre-existing databases (no-op when already present)."""
    # (table, column, definition) tuples to ensure exist
    _required_columns = [
        ("assembly", "created_at", "TEXT"),
        ("assembly", "finished_at", "TEXT DEFAULT NULL"),
        ("assembly", "runtime", "TEXT DEFAULT NULL"),
    ]
    for table, column, definition in _required_columns:
        existing = [row[1] for row in connection.execute(f'PRAGMA table_info("{table}")').fetchall()]
        # Only migrate when the table exists but the column is missing
        if existing and column not in existing:
            connection.execute(f'ALTER TABLE "{table}" ADD COLUMN {column} {definition}')
            connection.commit()


