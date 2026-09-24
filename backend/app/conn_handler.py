# Import future annotations for Pydantic models
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional

# Import general python packages
import os
import re
import threading
from datetime import datetime

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
                # Strip full-line SQL comments before matching so a CREATE TABLE preceded
                # by a header comment block (e.g. "-- Table structure for ...") is still found.
                uncommented = "\n".join(
                    l for l in statement.splitlines() if not l.strip().startswith("--")
                ).strip()
                match = _CREATE_TABLE_PATTERN.match(uncommented)
                if match:
                    table_name = next(group for group in match.groups() if group is not None)
                    if table_name not in existing_tables:
                        connection.execute(uncommented)
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
            # Keep migrations under the initialization lock so concurrent requests
            # cannot both attempt to add the same missing column.
            connection = sqlite3.connect(_DEFAULT_SQLITE_FILE, check_same_thread=False)
            connection.row_factory = sqlite3.Row   # column-name access on cursors
            connection.execute("PRAGMA foreign_keys = ON;")
            _apply_migrations(connection)
        return connection
    except sqlite3.Error as err:
        raise Exception(f"SQLite Connection Error: {err}") from err

# Apply lightweight, idempotent schema migrations to an existing database so that
# columns added to schema.sql after a DB was first created are backfilled in place.
def _apply_migrations(connection: sqlite3.Connection) -> None:
    """Add newer columns to pre-existing databases (no-op when already present)."""
    _migrate_status_update_schedule_intervals(connection)

    # (table, column, definition) tuples to ensure exist
    _required_columns = [
        ("assembly", "created_at", "TEXT"),
        ("assembly", "finished_at", "TEXT DEFAULT NULL"),
        ("assembly", "runtime", "TEXT DEFAULT NULL"),
        ("assembly", "keep_workdir", "BOOLEAN NOT NULL DEFAULT 0"),
        ("submission", "submission_portal", "TEXT NOT NULL"),
        ("submission", "database_status", "TEXT NOT NULL DEFAULT 'ACTIVE'"),
        ("submission", "gff_file", "BOOLEAN NOT NULL DEFAULT 0"),
        ("submission", "table2asn", "BOOLEAN NOT NULL DEFAULT 0"),
        ("submission", "number_of_samples", "INTEGER NOT NULL DEFAULT 0"),
        ("submission", "submitter_name", "TEXT DEFAULT NULL"),
        ("submission", "ncbi_publication_title", "TEXT DEFAULT NULL"),
        ("submission", "ncbi_publication_status", "TEXT NOT NULL DEFAULT 'Unpublished'"),
        ("submission", "ncbi_release_date", "TEXT DEFAULT NULL"),
        ("submission", "ncbi_submission_id", "TEXT DEFAULT NULL"),
        ("submission", "ncbi_submission_status", "TEXT DEFAULT NULL"),
        ("submission", "date_submitted", "TEXT DEFAULT NULL"),
        ("submission", "date_updated", "TEXT DEFAULT NULL"),
        ("submission", "comments", "TEXT DEFAULT NULL")
    ]
    # A stale "submission_id" TEXT column (an old external-accession field) collides with the
    # surrogate integer primary key the current schema expects under that same name — drop the
    # stale one and rename the real primary key ("submission_id_pk") into its place.
    submission_cols = [row[1] for row in connection.execute('PRAGMA table_info("submission")').fetchall()]
    if "submission_id_pk" in submission_cols:
        if "submission_id" in submission_cols:
            connection.execute('ALTER TABLE "submission" DROP COLUMN "submission_id"')
        connection.execute('ALTER TABLE "submission" RENAME COLUMN "submission_id_pk" TO "submission_id"')
        connection.commit()

    # Relax legacy NOT NULL constraints on fields that are legitimately absent before a
    # submission is sent, including GISAID rows created without optional credentials.
    nullable_col_notnull = {
        row[1]: row[3]
        for row in connection.execute('PRAGMA table_info("submission")').fetchall()
        if row[1] in ("submitter_name", "date_submitted", "date_updated")
    }
    if any(nullable_col_notnull.values()):
        _relax_submission_nullable_columns(connection)
    for table, column, definition in _required_columns:
        existing = [row[1] for row in connection.execute(f'PRAGMA table_info("{table}")').fetchall()]
        # Only migrate when the table exists but the column is missing
        if existing and column not in existing:
            connection.execute(f'ALTER TABLE "{table}" ADD COLUMN {column} {definition}')
            connection.commit()
    # (table, old_column, new_column) tuples to rename on pre-existing databases
    _required_renames = [
        ("submission", "db", "database"),
    ]
    for table, old_column, new_column in _required_renames:
        existing = [row[1] for row in connection.execute(f'PRAGMA table_info("{table}")').fetchall()]
        # Only rename when the old column is still present and the new one hasn't been added yet
        if old_column in existing and new_column not in existing:
            connection.execute(f'ALTER TABLE "{table}" RENAME COLUMN "{old_column}" TO "{new_column}"')
            connection.commit()

    _migrate_submission_database_status(connection)


# Migrate the submission table's database_status column from INACTIVE to ARCHIVED.
def _migrate_submission_database_status(connection: sqlite3.Connection) -> None:
    """Replace the legacy INACTIVE database status with ARCHIVED."""
    table_row = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='submission'"
    ).fetchone()
    if table_row is None or "INACTIVE" not in (table_row[0] or "").upper():
        return

    table_sql = table_row[0]
    migrated_sql = re.sub(r"(['\"])INACTIVE\1", "'ARCHIVED'", table_sql, flags=re.IGNORECASE)
    migrated_sql = re.sub(
        r'^\s*CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:"submission"|`submission`|\[submission\]|submission)',
        'CREATE TABLE "submission_status_migration"',
        migrated_sql,
        count=1,
        flags=re.IGNORECASE,
    )
    if migrated_sql == table_sql:
        return

    columns = [row[1] for row in connection.execute('PRAGMA table_info("submission")').fetchall()]
    column_list = ", ".join(f'"{column}"' for column in columns)
    select_list = ", ".join(
        (
            'CASE WHEN UPPER(TRIM("database_status")) = \'INACTIVE\' '
            'THEN \'ARCHIVED\' ELSE "database_status" END'
        ) if column == "database_status" else f'"{column}"'
        for column in columns
    )
    schema_objects = connection.execute(
        """
        SELECT sql FROM sqlite_master
        WHERE tbl_name = 'submission'
          AND type IN ('index', 'trigger')
          AND sql IS NOT NULL
        """
    ).fetchall()

    connection.commit()
    connection.execute("PRAGMA foreign_keys = OFF;")
    try:
        connection.execute("BEGIN")
        connection.execute('DROP TABLE IF EXISTS "submission_status_migration"')
        connection.execute(migrated_sql)
        connection.execute(
            f'INSERT INTO "submission_status_migration" ({column_list}) '
            f'SELECT {select_list} FROM "submission"'
        )
        connection.execute('DROP TABLE "submission"')
        connection.execute('ALTER TABLE "submission_status_migration" RENAME TO "submission"')
        for schema_object in schema_objects:
            connection.execute(schema_object[0])
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.execute("PRAGMA foreign_keys = ON;")

# Migrate the status_update_schedule table to allow one-to-four-hour intervals.
def _migrate_status_update_schedule_intervals(connection: sqlite3.Connection) -> None:
    """Allow one-to-four-hour intervals while preserving an existing schedule."""
    table_row = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='status_update_schedule'"
    ).fetchone()
    if table_row is None:
        return

    columns = [row[1] for row in connection.execute('PRAGMA table_info("status_update_schedule")').fetchall()]
    normalized_sql = " ".join((table_row[0] or "").lower().split())
    if "interval_minutes" in columns and "interval_minutes in (60, 120, 180, 240)" in normalized_sql:
        return

    existing = connection.execute("SELECT * FROM status_update_schedule WHERE schedule_id = 1").fetchone()
    existing_data = dict(existing) if existing is not None else None
    interval_minutes = existing_data.get("interval_minutes", 60) if existing_data is not None else 60
    if interval_minutes not in {60, 120, 180, 240}:
        interval_minutes = 60
    now = datetime.now(timezone.utc).isoformat()

    connection.execute('ALTER TABLE "status_update_schedule" RENAME TO "status_update_schedule_daily"')
    connection.execute(
        """
        CREATE TABLE status_update_schedule (
          schedule_id       INTEGER PRIMARY KEY CHECK (schedule_id = 1),
          enabled           INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
          frequency         TEXT NOT NULL DEFAULT 'hourly' CHECK (frequency = 'hourly'),
          interval_minutes  INTEGER NOT NULL DEFAULT 60 CHECK (interval_minutes IN (60, 120, 180, 240)),
          created_at        TEXT NOT NULL,
          updated_at        TEXT NOT NULL,
          last_run_at       TEXT DEFAULT NULL,
          last_run_status   TEXT DEFAULT NULL,
          last_run_message  TEXT DEFAULT NULL
        )
        """
    )
    if existing_data is not None:
        connection.execute(
            """
            INSERT INTO status_update_schedule (
                schedule_id, enabled, frequency, interval_minutes, created_at, updated_at,
                last_run_at, last_run_status, last_run_message
            ) VALUES (1, ?, 'hourly', ?, ?, ?, ?, ?, ?)
            """,
            (
                existing_data.get("enabled", 1),
                interval_minutes,
                existing_data.get("created_at") or now,
                now,
                existing_data.get("last_run_at"),
                existing_data.get("last_run_status"),
                existing_data.get("last_run_message"),
            ),
        )
    connection.execute('DROP TABLE "status_update_schedule_daily"')
    connection.commit()


# Rebuild the "submission" table so optional fields become nullable. SQLite has no ALTER COLUMN,
# so the table is renamed aside, recreated from its own patched DDL, repopulated, and dropped.
def _relax_submission_nullable_columns(connection: sqlite3.Connection) -> None:
    row = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='submission'"
    ).fetchone()
    if row is None:
        return
    relaxed_sql = re.sub(
        r"(date_submitted|date_updated)\s+TEXT\s+NOT\s+NULL\s+DEFAULT\s*\(\s*date\(\s*['\"]now['\"]\s*\)\s*\)",
        r"\1 TEXT DEFAULT NULL",
        row[0],
        flags=re.IGNORECASE,
    )
    relaxed_sql = re.sub(
        r"submitter_name\s+TEXT\s+NOT\s+NULL",
        "submitter_name TEXT DEFAULT NULL",
        relaxed_sql,
        flags=re.IGNORECASE,
    )
    if relaxed_sql == row[0]:
        return
    columns = [col[1] for col in connection.execute('PRAGMA table_info("submission")').fetchall()]
    column_list = ", ".join(f'"{col}"' for col in columns)
    connection.execute("PRAGMA foreign_keys = OFF;")
    connection.execute('ALTER TABLE "submission" RENAME TO "submission_pre_relax"')
    connection.execute(relaxed_sql)
    connection.execute(f'INSERT INTO "submission" ({column_list}) SELECT {column_list} FROM "submission_pre_relax"')
    connection.execute('DROP TABLE "submission_pre_relax"')
    connection.execute("PRAGMA foreign_keys = ON;")
    connection.commit()


    _normalize_finished_at(connection)


# One-time, idempotent data backfill for the assembly.finished_at column.
def _normalize_finished_at(connection: sqlite3.Connection) -> None:
    """Rewrite legacy finished_at values to a canonical, sortable form.

    Older runs stored finished_at in Nextflow's '%d-%b-%Y %H:%M:%S' shape
    (e.g. '27-Aug-2026 15:49:32'), which the frontend can't Date.parse or sort.
    Rewrite those to 'YYYY-MM-DD HH:MM:SS' so the load-run panel displays and
    orders them correctly. Already-canonical values fail this parse and are
    left untouched, so the pass is safe to run on every connection.
    """
    try:
        has_assembly = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='assembly'"
        ).fetchone()
        if not has_assembly:
            return
        rows = connection.execute(
            "SELECT assembly_id, finished_at FROM assembly WHERE finished_at IS NOT NULL"
        ).fetchall()
        for row in rows:
            raw = row["finished_at"]
            try:
                canon = datetime.strptime(str(raw), "%d-%b-%Y %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                continue
            if canon != raw:
                connection.execute(
                    "UPDATE assembly SET finished_at = ? WHERE assembly_id = ?",
                    (canon, row["assembly_id"]),
                )
        connection.commit()
    except sqlite3.Error:
        # Best-effort; a display-format backfill must never block DB startup
        pass


