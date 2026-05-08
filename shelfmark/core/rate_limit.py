"""Persistent login rate limiting backed by SQLite.

Replaces the in-memory `failed_login_attempts` dict in main.py so that
lockout state survives container restarts and works across processes.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from shelfmark.core.logger import setup_logger

if TYPE_CHECKING:
    pass

logger = setup_logger(__name__)

MAX_LOGIN_ATTEMPTS = 10
LOCKOUT_DURATION_MINUTES = 30
LOGIN_ATTEMPT_WARNING_THRESHOLD = 5


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _conn(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def cleanup_expired_lockouts(db_path: str) -> None:
    """Remove lockout rows whose lockout window has expired."""
    now = _utcnow().isoformat()
    with _conn(db_path) as conn:
        conn.execute(
            "DELETE FROM login_attempts WHERE locked_until IS NOT NULL AND locked_until < ?",
            (now,),
        )


def is_account_locked(db_path: str, username: str) -> bool:
    """Return True if the account is currently within an active lockout window."""
    cleanup_expired_lockouts(db_path)
    now = _utcnow().isoformat()
    with _conn(db_path) as conn:
        row = conn.execute(
            "SELECT locked_until FROM login_attempts WHERE username = ?",
            (username,),
        ).fetchone()
    if row is None:
        return False
    locked_until = row["locked_until"]
    return bool(locked_until and locked_until > now)


def record_failed_login(db_path: str, username: str, ip_address: str) -> bool:
    """Increment failed-attempt counter; lock the account when threshold is reached.

    Returns True if the account is now locked, False otherwise.
    """
    now = _utcnow()
    with _conn(db_path) as conn:
        conn.execute(
            """
            INSERT INTO login_attempts (username, attempt_count, last_attempt_at)
            VALUES (?, 1, ?)
            ON CONFLICT(username) DO UPDATE SET
                attempt_count = attempt_count + 1,
                last_attempt_at = excluded.last_attempt_at
            """,
            (username, now.isoformat()),
        )
        row = conn.execute(
            "SELECT attempt_count FROM login_attempts WHERE username = ?",
            (username,),
        ).fetchone()

    count = row["attempt_count"] if row else 1
    logger.warning(
        "Failed login attempt %s/%s for user '%s' from IP %s",
        count,
        MAX_LOGIN_ATTEMPTS,
        username,
        ip_address,
    )

    if count >= MAX_LOGIN_ATTEMPTS:
        locked_until = (now + timedelta(minutes=LOCKOUT_DURATION_MINUTES)).isoformat()
        with _conn(db_path) as conn:
            conn.execute(
                "UPDATE login_attempts SET locked_until = ? WHERE username = ?",
                (locked_until, username),
            )
        logger.warning(
            "Account locked for user '%s' until %s after %s failed attempts",
            username,
            locked_until,
            count,
        )
        return True

    return False


def clear_failed_logins(db_path: str, username: str) -> None:
    """Remove the attempt record for a user after a successful login."""
    with _conn(db_path) as conn:
        conn.execute("DELETE FROM login_attempts WHERE username = ?", (username,))
    logger.debug("Cleared failed login attempts for user: %s", username)


def get_attempt_count(db_path: str, username: str) -> int:
    """Return the current failed-attempt count for the user (0 if no record)."""
    with _conn(db_path) as conn:
        row = conn.execute(
            "SELECT attempt_count FROM login_attempts WHERE username = ?",
            (username,),
        ).fetchone()
    return int(row["attempt_count"]) if row else 0


def get_lockout_remaining_minutes(db_path: str, username: str) -> int | None:
    """Return minutes remaining in the lockout, or None if not locked."""
    now = _utcnow()
    with _conn(db_path) as conn:
        row = conn.execute(
            "SELECT locked_until FROM login_attempts WHERE username = ?",
            (username,),
        ).fetchone()
    if row is None or not row["locked_until"]:
        return None
    locked_until_str = row["locked_until"]
    try:
        locked_until = datetime.fromisoformat(locked_until_str)
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=UTC)
        remaining = (locked_until - now).total_seconds() / 60
        return max(1, int(remaining)) if remaining > 0 else None
    except ValueError:
        return None
