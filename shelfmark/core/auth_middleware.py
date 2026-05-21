"""Shared authentication middleware and decorators.

Extracted from main.py so that all route modules can import
``login_required`` and ``_resolve_status_scope`` without creating
circular imports.

Call ``configure(user_db, user_db_path)`` once during app-factory startup
before any routes are registered.
"""

from __future__ import annotations

from functools import wraps
from typing import TYPE_CHECKING, Any, Callable

from flask import jsonify, request, session
from werkzeug.wrappers import Response

from shelfmark.config.env import CWA_DB_PATH
from shelfmark.core.auth_modes import (
    is_settings_or_onboarding_path,
    load_active_auth_mode,
    requires_admin_for_settings_access,
)
from shelfmark.core.logger import setup_logger
from shelfmark.core.request_helpers import get_session_db_user_id

if TYPE_CHECKING:
    from shelfmark.core.user_db import UserDB

logger = setup_logger(__name__)

# ---------------------------------------------------------------------------
# Module-level state — set once by configure() in main.py's app factory.
# ---------------------------------------------------------------------------
_user_db: UserDB | None = None
_user_db_path: str = ""


def configure(user_db: UserDB | None, user_db_path: str) -> None:
    """Initialise the module with the active user DB instance and path."""
    global _user_db, _user_db_path
    _user_db = user_db
    _user_db_path = user_db_path


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def get_client_ip() -> str:
    """Extract client IP address from request, handling reverse proxy forwarding."""
    ip_address = request.headers.get("X-Forwarded-For", request.remote_addr) or "unknown"
    if "," in ip_address:
        ip_address = ip_address.split(",")[0].strip()
    return ip_address


def get_auth_mode() -> str:
    """Determine which authentication mode is active.

    Returns ``"none"`` when config is invalid or unavailable.
    """
    return load_active_auth_mode(CWA_DB_PATH, user_db=_user_db)


# ---------------------------------------------------------------------------
# Decorators
# ---------------------------------------------------------------------------


def login_required(
    f: Callable[..., Response | tuple[Response, int]],
) -> Callable[..., Response | tuple[Response, int]]:
    """Require authentication for a Flask route."""

    @wraps(f)
    def decorated_function(*args: object, **kwargs: object) -> Response | tuple[Response, int]:
        auth_mode = get_auth_mode()

        if auth_mode == "none":
            return f(*args, **kwargs)

        if auth_mode == "cwa" and CWA_DB_PATH and not CWA_DB_PATH.exists():
            logger.error("CWA database at %s is no longer accessible", CWA_DB_PATH)
            return jsonify({"error": "Internal Server Error"}), 500

        if "user_id" not in session:
            return jsonify({"error": "Unauthorized"}), 401

        # Check if admin has invalidated the user's sessions since they logged in.
        if _user_db is not None:
            from shelfmark.core.request_helpers import get_session_db_user_id
            db_uid = get_session_db_user_id(session)
            if db_uid is not None:
                login_time = session.get("login_at")
                if login_time is not None:
                    user_row = _user_db.get_user(user_id=db_uid)
                    if user_row:
                        invalidated_at = user_row.get("session_invalidated_at")
                        if invalidated_at and invalidated_at > login_time:
                            session.clear()
                            return jsonify({"error": "Session invalidated"}), 401

        if is_settings_or_onboarding_path(request.path):
            try:
                if requires_admin_for_settings_access(request.path, {}) and not session.get(
                    "is_admin", False
                ):
                    return jsonify({"error": "Admin access required"}), 403
            except (RuntimeError, TypeError, ValueError):
                logger.exception("Admin access check error")
                return jsonify({"error": "Internal Server Error"}), 500

        return f(*args, **kwargs)

    return decorated_function


# ---------------------------------------------------------------------------
# Status scope resolver (used by WebSocket handlers and status API)
# ---------------------------------------------------------------------------


def resolve_status_scope(*, require_authenticated: bool = True) -> tuple[bool, int | None, bool]:
    """Resolve queue-status visibility from the active session.

    Returns:
        ``(is_admin, db_user_id, can_access_status)``
    """
    auth_mode = get_auth_mode()
    if auth_mode == "none":
        return True, None, True

    if require_authenticated and "user_id" not in session:
        return False, None, False

    is_admin = bool(session.get("is_admin", False))
    if is_admin:
        return True, None, True

    db_user_id = get_session_db_user_id(session)
    if db_user_id is None:
        return False, None, False

    return False, db_user_id, True
