#!/usr/bin/env python3
"""
Simple key/value UI state store backed by the same SQLite DB as reports.

Used to persist lightweight UI state such as the batch processing queue so
that refreshing the browser does not lose state.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional
from datetime import datetime
import sqlite3

DEFAULT_DB_PATH = Path("./sync_reports/sync_reports.db")


def _ensure_parent(p: Path) -> None:
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass


def get_conn(db_path: Optional[Path] = None) -> sqlite3.Connection:
    dbp = Path(db_path or DEFAULT_DB_PATH)
    _ensure_parent(dbp)
    conn = sqlite3.connect(str(dbp))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def init_db(db_path: Optional[Path] = None) -> None:
    conn = get_conn(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ui_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


def set_state(key: str, value: Any, db_path: Optional[Path] = None) -> None:
    init_db(db_path)
    conn = get_conn(db_path)
    try:
        payload = json.dumps(value, ensure_ascii=False, default=str)
        ts = datetime.utcnow().isoformat()
        conn.execute(
            """
            INSERT INTO ui_state (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value=excluded.value,
                updated_at=excluded.updated_at
            ;
            """,
            (key, payload, ts),
        )
        conn.commit()
    finally:
        conn.close()


def get_state(key: str, db_path: Optional[Path] = None) -> Optional[Any]:
    init_db(db_path)
    conn = get_conn(db_path)
    try:
        cur = conn.execute("SELECT value FROM ui_state WHERE key = ? LIMIT 1", (key,))
        row = cur.fetchone()
        if not row:
            return None
        try:
            return json.loads(row[0])
        except Exception:
            return None
    finally:
        conn.close()


def delete_state(key: str, db_path: Optional[Path] = None) -> None:
    init_db(db_path)
    conn = get_conn(db_path)
    try:
        conn.execute("DELETE FROM ui_state WHERE key = ?", (key,))
        conn.commit()
    finally:
        conn.close()

