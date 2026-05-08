"""Shared API error-handling decorator.

Wraps route handlers to catch the standard operational errors and return a
uniform JSON error response, removing the ~40 duplicate try/except blocks
scattered across route modules.

Usage::

    from shelfmark.core.api_errors import handle_api_errors

    @app.route("/api/something")
    @login_required
    @handle_api_errors("something")
    def api_something():
        ...  # no try/except needed
"""

from __future__ import annotations

import sqlite3
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable

from shelfmark.core.logger import setup_logger

if TYPE_CHECKING:
    from flask import Response

logger = setup_logger(__name__)

# Mirror of the tuple in main.py — kept here so route modules can import it
# without importing from main.
OPERATIONAL_ERRORS = (OSError, RuntimeError, TypeError, ValueError, sqlite3.Error)
IMPORT_OPERATIONAL_ERRORS = (ImportError, *OPERATIONAL_ERRORS)


def handle_api_errors(
    label: str,
    *,
    include_import_errors: bool = False,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator that catches operational errors and returns a JSON 500 response.

    Args:
        label: Short description used in log messages (e.g. ``"releases search"``).
        include_import_errors: Also catch ``ImportError`` (for settings/plugin routes).
    """
    caught = IMPORT_OPERATIONAL_ERRORS if include_import_errors else OPERATIONAL_ERRORS

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return fn(*args, **kwargs)
            except caught as exc:  # type: ignore[misc]
                from flask import jsonify

                logger.error("API error [%s]: %s", label, exc)
                return jsonify({"error": str(exc)}), 500

        return wrapper

    return decorator
