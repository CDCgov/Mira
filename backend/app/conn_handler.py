# Import future annotations for Pydantic models
from __future__ import annotations
from typing import Optional

# Import general python packages
import os

# Import sqlite3 for database connection
import sqlite3

# Import schema_validator for default database path
from .schema_validator import _DEFAULT_SQLITE_FILE

# Function to open a SQLite connection from a handler
def init_connection() -> sqlite3.Connection:
    """Open and return a sqlite3 connection to the default database.

    Returns
    -------
    sqlite3.Connection
        An open connection with autocommit-style isolation level (check_same_thread=False).
    """
    try:
        connection = sqlite3.connect(_DEFAULT_SQLITE_FILE, check_same_thread=False)
        connection.row_factory = sqlite3.Row   # column-name access on cursors
        connection.execute("PRAGMA foreign_keys = ON;")
        return connection
    except sqlite3.Error as err:
        raise Exception(f"SQLite Connection Error: {err}") from err

        
