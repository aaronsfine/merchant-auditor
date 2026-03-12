"""
SQLite-backed error logging for CSV processing. No PII or raw CSV data is stored.
"""
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional

# Default path: project directory; override with PROCESSING_ERRORS_DB env
DB_PATH = os.environ.get("PROCESSING_ERRORS_DB", "processing_errors.db")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create ProcessingErrors table if it does not exist."""
    with _get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ProcessingErrors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                error_message TEXT NOT NULL,
                stack_trace TEXT,
                timestamp TEXT NOT NULL
            )
            """
        )
        conn.commit()


@contextmanager
def get_cursor():
    conn = _get_conn()
    try:
        yield conn.cursor()
        conn.commit()
    finally:
        conn.close()


def log_processing_error(
    session_id: str,
    error_message: str,
    stack_trace: Optional[str] = None,
) -> None:
    """
    Append a single error record. Caller must ensure error_message and stack_trace
    contain no PII or raw CSV data (only technical reason and row number).
    """
    now = datetime.now(timezone.utc).isoformat()
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO ProcessingErrors (session_id, error_message, stack_trace, timestamp)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, error_message, stack_trace or "", now),
        )
