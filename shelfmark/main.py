"""Flask app - app factory, middleware setup, and route registration."""

import logging
import os
import sqlite3
from importlib import import_module
from pathlib import Path
from typing import Any, cast

from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO
from werkzeug.middleware.proxy_fix import ProxyFix

from shelfmark.api.websocket import ws_manager
from shelfmark.config.env import (
    CONFIG_DIR,
    FLASK_HOST,
    FLASK_PORT,
    SESSION_COOKIE_NAME,
    SESSION_COOKIE_SECURE_ENV,
    _is_config_dir_writable,
    string_to_bool,
)
from shelfmark.config.security import _migrate_security_settings
from shelfmark.core.activity_view_state_service import ActivityViewStateService
from shelfmark.core.config import config as app_config
from shelfmark.core.download_history_service import DownloadHistoryService
from shelfmark.core.logger import setup_logger
from shelfmark.core.request_helpers import (
    emit_ws_event,
    normalize_optional_text,
)
from shelfmark.core.requests_service import sync_delivery_states_from_queue_status
from shelfmark.core.user_db import UserDB
from shelfmark.core import auth_middleware
from shelfmark.core.auth_middleware import get_auth_mode
from shelfmark.core.utils import normalize_base_path
from shelfmark.download import orchestrator as backend
from shelfmark.core.prefix_middleware import PrefixMiddleware

# New route-module registrars
from shelfmark.core.auth_routes import register_auth_routes
from shelfmark.core.static_routes import register_debug_routes, register_static_routes
from shelfmark.core.metadata_routes import register_metadata_routes
from shelfmark.core.download_routes import register_download_routes
from shelfmark.core.settings_routes import register_settings_routes
from shelfmark.core.websocket_handlers import register_websocket_handlers

logger = setup_logger(__name__)
FLASK_SECRET_KEY_MIN_BYTES = 32
_OPERATIONAL_ERRORS = (OSError, RuntimeError, TypeError, ValueError, sqlite3.Error)
_IMPORT_OPERATIONAL_ERRORS = (ImportError, *_OPERATIONAL_ERRORS)


def _is_debug_enabled() -> bool:
    debug_value = app_config.get("DEBUG", False)
    if isinstance(debug_value, str):
        return string_to_bool(debug_value)
    return bool(debug_value)


# Project root is the repository root above the package directory.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIST = PROJECT_ROOT / "frontend-dist"

BASE_PATH = normalize_base_path(normalize_optional_text(app_config.get("URL_BASE", "")))

app = Flask(__name__)
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0  # Disable caching
app.config["APPLICATION_ROOT"] = BASE_PATH or "/"
wsgi_app = cast(Any, ProxyFix(app.wsgi_app))
if BASE_PATH:
    wsgi_app = cast(Any, PrefixMiddleware(wsgi_app, BASE_PATH, bypass_paths={"/api/health"}))
app.wsgi_app = wsgi_app

# Socket.IO async mode.
# We run this app under Gunicorn with a gevent websocket worker (even when DEBUG=true),
# so Socket.IO should always use gevent here.
async_mode = "gevent"
socketio_cors_allowed_origins = "*"

# Initialize Flask-SocketIO with reverse proxy support
socketio_path = f"{BASE_PATH}/socket.io" if BASE_PATH else "/socket.io"
socketio_init_kwargs: dict[str, Any] = {
    "cors_allowed_origins": socketio_cors_allowed_origins,
    "async_mode": async_mode,
    "logger": False,
    "engineio_logger": False,
    # Reverse proxy / Traefik compatibility settings
    "path": socketio_path,
    "ping_timeout": 60,
    "ping_interval": 25,
    # Allow both websocket and polling for better compatibility
    "transports": ["websocket", "polling"],
    # Enable CORS for all origins (you can restrict this in production)
    "allow_upgrades": True,
    # Important for proxies that buffer
    "http_compression": True,
}
socketio = SocketIO(app, **socketio_init_kwargs)

# Initialize WebSocket manager
ws_manager.init_app(app, socketio)
ws_manager.set_queue_status_fn(backend.queue_status)
logger.info("Flask-SocketIO initialized with async_mode='%s'", async_mode)
logger.info("Socket.IO CORS allowed origins: %s", socketio_cors_allowed_origins)

# Ensure all plugins are loaded before starting the download coordinator.
# This prevents a race condition where the download loop could try to process
# a queued task before its handler (e.g., prowlarr) is registered.
try:
    import_module("shelfmark.metadata_providers")
    import_module("shelfmark.release_sources")
    logger.debug("Plugin modules loaded successfully")
except ImportError as e:
    logger.warning("Failed to import plugin modules: %s", e)

# Register all settings groups once at startup so that route handlers never
# need to call import_module() defensively on every request.
try:
    import_module("shelfmark.config.settings")
    import_module("shelfmark.config.notifications_settings")
    import_module("shelfmark.config.security")
    import_module("shelfmark.config.users_settings")
    logger.debug("Settings modules registered successfully")
except ImportError as e:
    logger.warning("Failed to register settings modules: %s", e)

# Migrate legacy security settings if needed
_migrate_security_settings()

# Initialize user database and register multi-user routes
# If CONFIG_DIR doesn't exist or is read-only, multi-user features will be disabled
_user_db_path = str(Path(os.environ.get("CONFIG_DIR", "/config")) / "users.db")
user_db: UserDB | None = None
download_history_service: DownloadHistoryService | None = None
activity_view_state_service: ActivityViewStateService | None = None
try:
    user_db = UserDB(_user_db_path)
    user_db.initialize()
    download_history_service = DownloadHistoryService(_user_db_path)
    activity_view_state_service = ActivityViewStateService(_user_db_path)
    import_module("shelfmark.config.users_settings")
    from shelfmark.core.admin_routes import register_admin_routes
    from shelfmark.core.oidc_routes import register_oidc_routes
    from shelfmark.core.self_user_routes import register_self_user_routes

    register_oidc_routes(app, user_db)
    register_admin_routes(app, user_db)
    register_self_user_routes(app, user_db)
except (sqlite3.OperationalError, OSError) as e:
    logger.warning(
        "User database initialization failed: %s. Multi-user authentication features will be disabled. Ensure CONFIG_DIR (%s) exists and is writable.",
        e,
        os.environ.get("CONFIG_DIR", "/config"),
    )
    user_db = None
    download_history_service = None
    activity_view_state_service = None

# Wire auth_middleware with the resolved user_db so login_required and
# get_auth_mode() are consistent across all route modules.
auth_middleware.configure(user_db, _user_db_path)

# Start download coordinator
backend.start()


def _emit_request_update_events(updated_requests: list[dict[str, Any]]) -> None:
    """Broadcast request_update events for rows changed by delivery-state sync."""
    if not updated_requests or ws_manager is None:
        return

    for updated in updated_requests:
        payload = {
            "request_id": updated["id"],
            "status": updated["status"],
            "delivery_state": updated.get("delivery_state"),
            "title": (updated.get("book_data") or {}).get("title") or "Unknown title",
        }
        emit_ws_event(
            ws_manager,
            event_name="request_update",
            room=f"user_{updated['user_id']}",
            payload=payload,
        )
        emit_ws_event(
            ws_manager,
            event_name="request_update",
            room="admins",
            payload=payload,
        )


def _resolve_auth_mode_for_routes() -> str:
    """Resolve auth mode lazily so tests and runtime patches still take effect."""
    return get_auth_mode()


def _queue_release_for_routes(*args: Any, **kwargs: Any) -> Any:
    """Queue a release via the current backend instance."""
    return backend.queue_release(*args, **kwargs)


def _queue_status_for_routes(user_id: int | None = None) -> dict[str, dict[str, Any]]:
    """Read queue status via the current backend instance."""
    return backend.queue_status(user_id=user_id)


if user_db is not None:
    try:
        from shelfmark.core.activity_routes import register_activity_routes
        from shelfmark.core.request_routes import register_request_routes

        register_request_routes(
            app,
            user_db,
            resolve_auth_mode=_resolve_auth_mode_for_routes,
            queue_release=_queue_release_for_routes,
            ws_manager=ws_manager,
        )
        if download_history_service is not None and activity_view_state_service is not None:
            register_activity_routes(
                app,
                user_db,
                activity_view_state_service=activity_view_state_service,
                download_history_service=download_history_service,
                resolve_auth_mode=_resolve_auth_mode_for_routes,
                queue_status=_queue_status_for_routes,
                sync_request_delivery_states=sync_delivery_states_from_queue_status,
                emit_request_updates=_emit_request_update_events,
                ws_manager=ws_manager,
            )
    except _IMPORT_OPERATIONAL_ERRORS as e:
        logger.warning("Failed to register request routes: %s", e)


# Enable CORS in development mode for local frontend development
if _is_debug_enabled():
    CORS(
        app,
        resources={
            r"/*": {
                "origins": ["http://localhost:5173", "http://127.0.0.1:5173"],
                "supports_credentials": True,
                "allow_headers": ["Content-Type", "Authorization"],
                "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            }
        },
    )


# Custom log filter to exclude routine status endpoint polling and WebSocket noise
class LogNoiseFilter(logging.Filter):
    """Filter out routine status endpoint requests and WebSocket upgrade errors to reduce log noise.

    WebSocket upgrade errors are benign - Flask-SocketIO automatically falls back to polling transport.
    The error occurs because Werkzeug's built-in server doesn't fully support WebSocket upgrades.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Return whether a log record should be emitted."""
        message = record.getMessage() if hasattr(record, "getMessage") else str(record.msg)

        # Exclude GET /api/status requests (polling noise)
        if "GET /api/status" in message:
            return False

        # Exclude WebSocket upgrade errors (benign - falls back to polling)
        if "write() before start_response" in message:
            return False

        # Exclude the Error on request line that precedes WebSocket errors
        if record.levelno == logging.ERROR:
            if "Error on request:" in message:
                return False
            # Filter WebSocket-related AssertionError tracebacks
            if hasattr(record, "exc_info") and record.exc_info:
                exc_type, exc_value = record.exc_info[0], record.exc_info[1]
                if (
                    exc_type
                    and exc_type.__name__ == "AssertionError"
                    and exc_value
                    and "write() before start_response" in str(exc_value)
                ):
                    return False

        return True


# Flask logger
app.logger.handlers = logger.handlers
app.logger.setLevel(logger.level)
# Also handle Werkzeug's logger
werkzeug_logger = logging.getLogger("werkzeug")
werkzeug_logger.handlers = logger.handlers
werkzeug_logger.setLevel(logger.level)
# Add filter to suppress routine status endpoint polling logs and WebSocket upgrade errors
werkzeug_logger.addFilter(LogNoiseFilter())

# Set up authentication defaults
SESSION_COOKIE_SECURE = string_to_bool(SESSION_COOKIE_SECURE_ENV)


def _load_or_create_secret_key() -> bytes:
    """Load a persisted Flask secret key from config, or create one."""
    secret_path = CONFIG_DIR / ".flask_secret"

    try:
        if secret_path.exists():
            secret_key = secret_path.read_bytes()
            if len(secret_key) >= FLASK_SECRET_KEY_MIN_BYTES:
                return secret_key
            logger.warning(
                "Invalid persisted Flask secret key at %s (length=%s). Regenerating.",
                secret_path,
                len(secret_key),
            )
    except OSError as exc:
        logger.warning("Failed to read Flask secret key at %s: %s", secret_path, exc)

    secret_key = os.urandom(64)
    try:
        secret_path.parent.mkdir(parents=True, exist_ok=True)
        secret_path.write_bytes(secret_key)
        secret_path.chmod(0o600)
    except OSError as exc:
        logger.warning(
            "Failed to persist Flask secret key at %s. Sessions may reset on restart: %s",
            secret_path,
            exc,
        )

    return secret_key


app.config.update(
    SECRET_KEY=_load_or_create_secret_key(),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=SESSION_COOKIE_SECURE,
    SESSION_COOKIE_NAME=SESSION_COOKIE_NAME,
    PERMANENT_SESSION_LIFETIME=604800,  # 7 days in seconds
)

logger.info(
    "Session cookie secure setting: %s (from env: %s)",
    SESSION_COOKIE_SECURE,
    SESSION_COOKIE_SECURE_ENV,
)
logger.info("Session cookie name: %s", SESSION_COOKIE_NAME)

# ---------------------------------------------------------------------------
# Register route modules
# ---------------------------------------------------------------------------

register_auth_routes(app, user_db, _user_db_path)
register_static_routes(app, FRONTEND_DIST, BASE_PATH)
register_debug_routes(app, _is_debug_enabled())
register_metadata_routes(app)
register_download_routes(
    app, user_db, download_history_service, ws_manager, backend, activity_view_state_service
)
register_settings_routes(app)
register_websocket_handlers(socketio, backend, ws_manager)

logger.log_resource_usage()

# Warn if config directory is not writable (settings won't persist)
if not _is_config_dir_writable():
    logger.warning(
        "Config directory %s is not writable. Settings will not persist. Mount a config volume to enable settings persistence (see docs for details).",
        CONFIG_DIR,
    )

if __name__ == "__main__":
    debug_enabled = _is_debug_enabled()
    logger.info(
        "Starting Flask application with WebSocket support on %s:%s (debug=%s)",
        FLASK_HOST,
        FLASK_PORT,
        debug_enabled,
    )
    socketio.run(
        app,
        host=FLASK_HOST,
        port=FLASK_PORT,
        debug=debug_enabled,
        allow_unsafe_werkzeug=True,  # For development only
    )
