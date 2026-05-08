"""WebSocket (Socket.IO) event handlers.

Registers connect, disconnect, and request_status event handlers on the
provided SocketIO instance.
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING, Any

from flask import request
from flask_socketio import emit

from shelfmark.core.auth_middleware import resolve_status_scope
from shelfmark.core.logger import setup_logger

if TYPE_CHECKING:
    from flask_socketio import SocketIO

    from shelfmark.api.websocket import WebSocketManager
    from shelfmark.download import orchestrator as OrchestratorType

logger = setup_logger(__name__)

_OPERATIONAL_ERRORS = (OSError, RuntimeError, TypeError, ValueError, sqlite3.Error)


def _get_request_sid() -> str | None:
    """Return the Socket.IO session id for the active request when available."""
    sid = getattr(request, "sid", None)
    return sid if isinstance(sid, str) and sid else None


def register_websocket_handlers(
    socketio: "SocketIO",
    backend: "OrchestratorType",
    ws_manager: "WebSocketManager",
) -> None:
    """Register Socket.IO event handlers on the provided SocketIO instance."""

    def handle_connect() -> None:
        """Handle client connection."""
        logger.info("WebSocket client connected")

        # Track the connection (triggers warmup callbacks on first connect)
        ws_manager.client_connected()

        # Join appropriate room based on authenticated user session
        is_admin, db_user_id, can_access_status = resolve_status_scope()
        sid = _get_request_sid()
        if sid is None:
            logger.warning("Socket.IO connect event missing sid")
            return
        ws_manager.join_user_room(sid, is_admin=is_admin, db_user_id=db_user_id)

        # Send initial status to the newly connected client (filtered)
        try:
            if not can_access_status:
                emit("status_update", {})
                return

            user_id = None if is_admin else db_user_id
            status = backend.queue_status(user_id=user_id)
            emit("status_update", status)
        except _OPERATIONAL_ERRORS:
            logger.exception("Error sending initial status")

    def handle_disconnect() -> None:
        """Handle client disconnection."""
        logger.info("WebSocket client disconnected")

        # Leave room
        sid = _get_request_sid()
        if sid is not None:
            ws_manager.leave_user_room(sid)

        # Track the disconnection
        ws_manager.client_disconnected()

    def handle_status_request() -> None:
        """Handle manual status request from client."""
        try:
            is_admin, db_user_id, can_access_status = resolve_status_scope()
            sid = _get_request_sid()
            if sid is None:
                logger.warning("Socket.IO request_status event missing sid")
                emit("status_update", {})
                return
            ws_manager.sync_user_room(sid, is_admin=is_admin, db_user_id=db_user_id)

            if not can_access_status:
                emit("status_update", {})
                return

            user_id = None if is_admin else db_user_id
            status = backend.queue_status(user_id=user_id)
            emit("status_update", status)
        except _OPERATIONAL_ERRORS:
            logger.exception("Error handling status request")
            emit("error", {"message": "Failed to get status"})

    socketio.on("connect")(handle_connect)
    socketio.on("disconnect")(handle_disconnect)
    socketio.on("request_status")(handle_status_request)
