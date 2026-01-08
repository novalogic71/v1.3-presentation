#!/usr/bin/env python3
"""
Job persistence layer for tracking analysis jobs in SQLite.

Provides persistent storage for job lifecycle management, enabling
reconnection to in-progress jobs after page refresh or server restart.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Use absolute path to ensure consistency regardless of working directory
# Database is stored in the project's sync_reports folder
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DB_PATH = _PROJECT_ROOT / "sync_reports" / "sync_reports.db"


def _ensure_parent(p: Path) -> None:
    """Ensure parent directory exists."""
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass


def get_conn(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Get SQLite connection with WAL mode enabled."""
    dbp = Path(db_path or DEFAULT_DB_PATH)
    _ensure_parent(dbp)
    conn = sqlite3.connect(str(dbp))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    # Enable row factory for dict-like access
    conn.row_factory = sqlite3.Row
    return conn


def migrate_database(db_path: Optional[Path] = None) -> None:
    """
    Create jobs table if it doesn't exist.

    This is safe to call on every startup - CREATE TABLE IF NOT EXISTS
    will only create the table if it's missing.
    """
    conn = get_conn(db_path)
    try:
        # Create jobs table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                job_type TEXT NOT NULL,
                status TEXT NOT NULL,
                progress REAL DEFAULT 0.0,
                status_message TEXT,
                request_params TEXT NOT NULL,
                result_data TEXT,
                error_message TEXT,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                updated_at TEXT NOT NULL,
                server_pid INTEGER
            );
            """
        )

        # Create indexes for efficient queries
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status, created_at DESC);"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at DESC);"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_jobs_type_status ON jobs(job_type, status);"
        )

        conn.commit()
    finally:
        conn.close()


def create_job(
    job_id: str,
    job_type: str,
    request_params: Dict[str, Any],
    parent_batch_id: Optional[str] = None,
    db_path: Optional[Path] = None
) -> None:
    """
    Create a new job record in pending state.

    Args:
        job_id: Unique job identifier (e.g., analysis_20250105_143052_abc123)
        job_type: 'single' or 'batch_item'
        request_params: Dictionary of request parameters (will be JSON serialized)
        parent_batch_id: Optional batch ID if this is a batch item
        db_path: Optional database path
    """
    conn = get_conn(db_path)
    try:
        now = datetime.utcnow().isoformat()
        conn.execute(
            """
            INSERT INTO jobs (
                job_id, job_type, status, progress, request_params,
                created_at, updated_at, server_pid
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                job_type,
                'pending',
                0.0,
                json.dumps(request_params, default=str),
                now,
                now,
                os.getpid()
            )
        )
        conn.commit()
    finally:
        conn.close()


def update_job_status(
    job_id: str,
    status: Optional[str] = None,
    progress: Optional[float] = None,
    status_message: Optional[str] = None,
    db_path: Optional[Path] = None
) -> None:
    """
    Update job status, progress, and/or status message.

    Args:
        job_id: Job identifier
        status: New status (pending, processing, completed, failed, orphaned, cancelled)
        progress: Progress percentage (0.0 to 100.0)
        status_message: Human-readable status message
        db_path: Optional database path
    """
    conn = get_conn(db_path)
    try:
        updates = []
        params = []

        if status is not None:
            updates.append("status = ?")
            params.append(status)

            # Set started_at when transitioning to processing
            if status == 'processing':
                updates.append("started_at = ?")
                params.append(datetime.utcnow().isoformat())

        if progress is not None:
            updates.append("progress = ?")
            params.append(float(progress))

        if status_message is not None:
            updates.append("status_message = ?")
            params.append(status_message)

        if not updates:
            return  # Nothing to update

        # Always update updated_at
        updates.append("updated_at = ?")
        params.append(datetime.utcnow().isoformat())

        # Add job_id as final parameter
        params.append(job_id)

        query = f"UPDATE jobs SET {', '.join(updates)} WHERE job_id = ?"
        conn.execute(query, params)
        conn.commit()
    finally:
        conn.close()


def complete_job(
    job_id: str,
    result_data: Dict[str, Any],
    db_path: Optional[Path] = None
) -> None:
    """
    Mark job as completed and store result data.

    Args:
        job_id: Job identifier
        result_data: Result dictionary (will be JSON serialized)
        db_path: Optional database path
    """
    conn = get_conn(db_path)
    try:
        now = datetime.utcnow().isoformat()
        conn.execute(
            """
            UPDATE jobs
            SET status = ?,
                progress = ?,
                result_data = ?,
                completed_at = ?,
                updated_at = ?
            WHERE job_id = ?
            """,
            (
                'completed',
                100.0,
                json.dumps(result_data, default=str),
                now,
                now,
                job_id
            )
        )
        conn.commit()
    finally:
        conn.close()


def fail_job(
    job_id: str,
    error_message: str,
    db_path: Optional[Path] = None
) -> None:
    """
    Mark job as failed with error message.

    Args:
        job_id: Job identifier
        error_message: Error description
        db_path: Optional database path
    """
    conn = get_conn(db_path)
    try:
        now = datetime.utcnow().isoformat()
        conn.execute(
            """
            UPDATE jobs
            SET status = ?,
                error_message = ?,
                completed_at = ?,
                updated_at = ?
            WHERE job_id = ?
            """,
            (
                'failed',
                error_message,
                now,
                now,
                job_id
            )
        )
        conn.commit()
    finally:
        conn.close()


def get_job(job_id: str, db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """
    Retrieve job by ID.

    Args:
        job_id: Job identifier
        db_path: Optional database path

    Returns:
        Dictionary with job data or None if not found
    """
    conn = get_conn(db_path)
    try:
        cursor = conn.execute(
            "SELECT * FROM jobs WHERE job_id = ?",
            (job_id,)
        )
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    finally:
        conn.close()


def list_jobs(
    status: Optional[str] = None,
    job_type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db_path: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """
    List jobs with optional filters.

    Args:
        status: Filter by status (pending, processing, completed, failed, orphaned)
        job_type: Filter by job type (single, batch_item)
        limit: Maximum number of results
        offset: Offset for pagination
        db_path: Optional database path

    Returns:
        List of job dictionaries
    """
    conn = get_conn(db_path)
    try:
        query = "SELECT * FROM jobs WHERE 1=1"
        params = []

        if status:
            query += " AND status = ?"
            params.append(status)

        if job_type:
            query += " AND job_type = ?"
            params.append(job_type)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor = conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def find_orphaned_jobs(db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """
    Find jobs in processing/pending state with dead server_pid.

    A job is considered orphaned if:
    1. Status is 'processing' or 'pending'
    2. server_pid is not None
    3. Process with server_pid is not running

    Args:
        db_path: Optional database path

    Returns:
        List of orphaned job dictionaries
    """
    conn = get_conn(db_path)
    try:
        cursor = conn.execute(
            """
            SELECT * FROM jobs
            WHERE status IN ('processing', 'pending')
            AND server_pid IS NOT NULL
            ORDER BY created_at DESC
            """
        )

        orphaned = []
        for row in cursor.fetchall():
            job = dict(row)
            pid = job.get('server_pid')

            if pid and not _is_process_running(pid):
                orphaned.append(job)

        return orphaned
    finally:
        conn.close()


def mark_orphaned_jobs(db_path: Optional[Path] = None) -> int:
    """
    Mark jobs with dead server_pid as orphaned.

    This should be called on service startup to detect jobs
    from previous server instances that didn't complete.

    Args:
        db_path: Optional database path

    Returns:
        Number of jobs marked as orphaned
    """
    orphaned_jobs = find_orphaned_jobs(db_path)

    if not orphaned_jobs:
        return 0

    conn = get_conn(db_path)
    try:
        now = datetime.utcnow().isoformat()
        count = 0

        for job in orphaned_jobs:
            conn.execute(
                """
                UPDATE jobs
                SET status = ?,
                    error_message = ?,
                    updated_at = ?
                WHERE job_id = ?
                """,
                (
                    'orphaned',
                    'Server restarted during processing',
                    now,
                    job['job_id']
                )
            )
            count += 1

        conn.commit()
        return count
    finally:
        conn.close()


def _is_process_running(pid: int) -> bool:
    """
    Check if a process with given PID is running.

    Args:
        pid: Process ID

    Returns:
        True if process is running, False otherwise
    """
    try:
        # On Unix, os.kill(pid, 0) doesn't actually kill the process,
        # it just checks if we can send a signal to it
        os.kill(pid, 0)
        return True
    except OSError:
        return False
    except Exception:
        # On Windows or other platforms, this might not work
        # In that case, assume the process is dead
        return False


def delete_old_jobs(
    days_to_keep: int = 30,
    keep_failed: bool = True,
    db_path: Optional[Path] = None
) -> int:
    """
    Delete completed jobs older than specified days.

    Useful for periodic cleanup to prevent database growth.

    Args:
        days_to_keep: Keep jobs from last N days
        keep_failed: If True, don't delete failed/orphaned jobs (for troubleshooting)
        db_path: Optional database path

    Returns:
        Number of jobs deleted
    """
    from datetime import timedelta

    conn = get_conn(db_path)
    try:
        cutoff_date = (datetime.utcnow() - timedelta(days=days_to_keep)).isoformat()

        if keep_failed:
            query = """
                DELETE FROM jobs
                WHERE created_at < ?
                AND status IN ('completed', 'cancelled')
            """
        else:
            query = """
                DELETE FROM jobs
                WHERE created_at < ?
            """

        cursor = conn.execute(query, (cutoff_date,))
        deleted = cursor.rowcount
        conn.commit()

        return deleted
    finally:
        conn.close()
