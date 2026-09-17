from __future__ import annotations

# Standard library imports.
import asyncio
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from typing import Any

# Import necessary modules and functions.
from .conn_handler import init_connection
from .logging_config import logger
from .seqsender_handler import check_seqsender_submission
from .sqlite_handler import lookup_tbl_in_database

# Internal variables for the status update scheduler.
_scheduler_task: asyncio.Task[None] | None = None
_scheduler_wakeup: asyncio.Event | None = None
_run_lock: asyncio.Lock | None = None

# Get the current UTC time.
def _utc_now() -> datetime:
    return datetime.now(timezone.utc)

# Calculate the next hourly run. Missed runs while the backend was stopped are skipped.
def _next_run_at(
    last_run_at: str | None,
    updated_at: str | None,
    now: datetime | None = None,
    interval_minutes: int = 60,
) -> datetime:
    current = now or _utc_now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    else:
        current = current.astimezone(timezone.utc)

    anchor_text = last_run_at or updated_at
    if anchor_text:
        anchor = datetime.fromisoformat(anchor_text)
        if anchor.tzinfo is None:
            anchor = anchor.replace(tzinfo=timezone.utc)
        else:
            anchor = anchor.astimezone(timezone.utc)
        candidate = anchor + timedelta(minutes=interval_minutes)
        if candidate > current:
            return candidate
    return current + timedelta(minutes=interval_minutes)

# Retrieve the current status update schedule from the database.
def get_status_update_schedule() -> dict[str, Any]:
    connection = init_connection()
    try:
        row = connection.execute(
            "SELECT * FROM status_update_schedule WHERE schedule_id = 1"
        ).fetchone()
    finally:
        connection.close()

    if row is None:
        return {"enabled": False, "frequency": "hourly", "interval_minutes": 60, "schedule": None}

    schedule = dict(row)
    schedule["enabled"] = bool(schedule["enabled"])
    schedule["next_run_at"] = _next_run_at(
        schedule.get("last_run_at"),
        schedule.get("updated_at"),
        interval_minutes=schedule["interval_minutes"],
    ).isoformat()
    return schedule

# Save the status update schedule to the database.
def save_status_update_schedule(interval_hours: int = 1) -> dict[str, Any]:
    if interval_hours not in {1, 2, 3, 4}:
        raise ValueError("Status update interval must be between 1 and 4 hours.")
    interval_minutes = interval_hours * 60
    now = _utc_now().isoformat()
    connection = init_connection()
    try:
        connection.execute(
            """
            INSERT INTO status_update_schedule (
                schedule_id, enabled, frequency, interval_minutes, created_at, updated_at
            ) VALUES (1, 1, 'hourly', ?, ?, ?)
            ON CONFLICT(schedule_id) DO UPDATE SET
                enabled = 1,
                frequency = 'hourly',
                interval_minutes = excluded.interval_minutes,
                updated_at = excluded.updated_at
            """,
            (interval_minutes, now, now),
        )
        connection.commit()
    finally:
        connection.close()
    return get_status_update_schedule()

# Delete the status update schedule from the database.
def delete_status_update_schedule() -> None:
    connection = init_connection()
    try:
        connection.execute("DELETE FROM status_update_schedule WHERE schedule_id = 1")
        connection.commit()
    finally:
        connection.close()

# Record the result of a status update run.
def _record_run(status: str, message: str) -> None:
    connection = init_connection()
    try:
        connection.execute(
            """
            UPDATE status_update_schedule
            SET last_run_at = ?, last_run_status = ?, last_run_message = ?, updated_at = ?
            WHERE schedule_id = 1
            """,
            (_utc_now().isoformat(), status, message, _utc_now().isoformat()),
        )
        connection.commit()
    finally:
        connection.close()

# Update the statuses of all submissions.
def update_all_submission_statuses() -> dict[str, Any]:
    submission_table = lookup_tbl_in_database(
        db_tbl_name=["submission"],
        return_var=["submission_name", "organism", "database", "submission_type", "submission_status"],
        filter_coln_var=["database_status"],
        filter_coln_val={"database_status": ["ACTIVE"]},
    )
    grouped: dict[tuple[str, str, str], set[str]] = {}
    skipped_created: set[tuple[str, str, str]] = set()

    for row in submission_table.to_dicts():
        key = (row["submission_name"], row["organism"], row["submission_type"])
        if str(row["submission_status"]).strip().upper() == "CREATED":
            skipped_created.add(key)
            grouped.pop(key, None)
            continue
        if key not in skipped_created:
            grouped.setdefault(key, set()).add(row["database"])

    succeeded = 0
    failures: list[str] = []
    for (submission_name, organism, submission_type), databases in grouped.items():
        try:
            result = check_seqsender_submission(
                submission_name=submission_name,
                organism=organism,
                database=sorted(databases),
                submission_type=submission_type,
            )
            if result.get("status") == "FAILED":
                failures.append(f"{submission_name}: {result.get('message', 'status check failed')}")
            else:
                succeeded += 1
        except Exception as err:
            failures.append(f"{submission_name}: {err}")

    summary = {
        "checked": len(grouped),
        "succeeded": succeeded,
        "failed": len(failures),
        "skipped_created": len(skipped_created),
        "errors": failures,
    }
    run_status = "success" if not failures else "partial_failure"
    message = (
        f"Checked {len(grouped)} submission(s): {succeeded} succeeded, "
        f"{len(failures)} failed, {len(skipped_created)} not yet submitted."
    )
    _record_run(run_status, message)
    logger.info("Scheduled submission status update finished: %s", message)
    return summary

# The main loop for the status update scheduler.
async def _scheduler_loop() -> None:
    assert _scheduler_wakeup is not None
    assert _run_lock is not None
    while True:
        schedule = await asyncio.to_thread(get_status_update_schedule)
        if not schedule.get("enabled"):
            await _scheduler_wakeup.wait()
            _scheduler_wakeup.clear()
            continue

        next_run = _next_run_at(
            schedule.get("last_run_at"),
            schedule.get("updated_at"),
            interval_minutes=schedule["interval_minutes"],
        )
        delay = max(0.0, (next_run - _utc_now()).total_seconds())
        try:
            await asyncio.wait_for(_scheduler_wakeup.wait(), timeout=delay)
            _scheduler_wakeup.clear()
            continue
        except asyncio.TimeoutError:
            pass

        async with _run_lock:
            try:
                await asyncio.to_thread(update_all_submission_statuses)
            except Exception:
                logger.exception("Scheduled submission status update failed before completion.")
                await asyncio.to_thread(_record_run, "failed", "The scheduled status update failed before completion.")

# Start the status update scheduler.
def start_status_update_scheduler() -> None:
    global _scheduler_task, _scheduler_wakeup, _run_lock
    if _scheduler_task is not None and not _scheduler_task.done():
        return
    _scheduler_wakeup = asyncio.Event()
    _run_lock = asyncio.Lock()
    _scheduler_task = asyncio.create_task(_scheduler_loop(), name="submission-status-scheduler")

# Stop the status update scheduler.
async def stop_status_update_scheduler() -> None:
    global _scheduler_task, _scheduler_wakeup, _run_lock
    if _scheduler_task is not None:
        _scheduler_task.cancel()
        with suppress(asyncio.CancelledError):
            await _scheduler_task
    _scheduler_task = None
    _scheduler_wakeup = None
    _run_lock = None


# Wake up the status update scheduler if it is waiting.
def wake_status_update_scheduler() -> None:
    if _scheduler_wakeup is not None:
        _scheduler_wakeup.set()