"""Download queue, status, and cover-proxy API routes.

Registers all download-related endpoints together with the orchestrator callback
hooks (_record_download_queued, _record_download_terminal_snapshot) that write
to download history and emit WebSocket events.
"""

from __future__ import annotations

import io
import re
import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING, Any

from flask import Flask, Response, jsonify, request, send_file, session

from shelfmark.core.auth_middleware import get_auth_mode, login_required, resolve_status_scope
from shelfmark.core.logger import setup_logger
from shelfmark.core.models import TERMINAL_QUEUE_STATUSES, QueueStatus
from shelfmark.core.notifications import (
    NotificationContext,
    NotificationEvent,
    notify_admin,
    notify_user,
)
from shelfmark.core.request_helpers import (
    coerce_bool,
    emit_ws_event,
    load_users_request_policy_settings,
    normalize_optional_text,
    normalize_positive_int,
)
from shelfmark.core.request_policy import (
    PolicyMode,
    get_source_content_type_capabilities,
    merge_request_policy_settings,
    normalize_content_type,
    normalize_source,
    resolve_policy_mode,
)
from shelfmark.core.requests_service import (
    reopen_failed_request,
    sync_delivery_states_from_queue_status,
)
from shelfmark.release_sources import get_source_display_name

if TYPE_CHECKING:
    from shelfmark.api.websocket import WebSocketManager
    from shelfmark.core.activity_view_state_service import ActivityViewStateService
    from shelfmark.core.download_history_service import DownloadHistoryService
    from shelfmark.core.user_db import UserDB
    from shelfmark.download import orchestrator as OrchestratorType

logger = setup_logger(__name__)

_OPERATIONAL_ERRORS = (OSError, RuntimeError, TypeError, ValueError, sqlite3.Error)
_IMPORT_OPERATIONAL_ERRORS = (ImportError, *_OPERATIONAL_ERRORS)

_AUDIOBOOK_CATEGORY_RANGE = (3030, 3049)
_AUDIOBOOK_FORMAT_HINTS = frozenset(
    {
        "m4b",
        "mp3",
        "m4a",
        "flac",
        "ogg",
        "wma",
        "aac",
        "wav",
        "opus",
    }
)


def _contains_audiobook_format_hint(value: Any) -> bool:
    if not isinstance(value, str):
        return False

    normalized = value.strip().lower()
    if not normalized:
        return False

    tokens = [token for token in re.split(r"[^a-z0-9]+", normalized) if token]
    return any(token in _AUDIOBOOK_FORMAT_HINTS for token in tokens)


def register_download_routes(
    app: Flask,
    user_db: "UserDB | None",
    download_history_service: "DownloadHistoryService | None",
    ws_manager: "WebSocketManager",
    backend: "OrchestratorType",
    activity_view_state_service: "ActivityViewStateService | None" = None,
) -> None:
    """Register download queue, status, and cover routes on the Flask app."""

    # -------------------------------------------------------------------------
    # Helper functions (closed over captured parameters)
    # -------------------------------------------------------------------------

    def _resolve_release_content_type(data: dict[str, Any], source: Any) -> tuple[str, bool]:
        """Resolve release content type for policy checks and queue payload normalization."""
        extra = data.get("extra")
        if not isinstance(extra, dict):
            extra = {}

        explicit_content_type = data.get("content_type")
        if explicit_content_type is None:
            explicit_content_type = extra.get("content_type")
        if explicit_content_type is not None:
            return normalize_content_type(explicit_content_type), False

        categories = extra.get("categories")
        if isinstance(categories, list):
            min_cat, max_cat = _AUDIOBOOK_CATEGORY_RANGE
            for raw_category in categories:
                try:
                    category_id = int(raw_category)
                except (TypeError, ValueError):
                    continue
                if min_cat <= category_id <= max_cat:
                    return "audiobook", True

        candidates: list[Any] = [
            data.get("format"),
            extra.get("format"),
            extra.get("formats_display"),
            data.get("title"),
        ]
        formats = extra.get("formats")
        if isinstance(formats, list):
            candidates.extend(formats)
        else:
            candidates.append(formats)

        if any(_contains_audiobook_format_hint(candidate) for candidate in candidates):
            return "audiobook", True

        capabilities = get_source_content_type_capabilities()
        supported = capabilities.get(normalize_source(source))
        if supported and len(supported) == 1:
            return normalize_content_type(next(iter(supported))), True

        return "ebook", False

    def _resolve_policy_mode_for_current_user(*, source: Any, content_type: Any) -> PolicyMode | None:
        """Resolve policy mode for current session, or None when policy guard is bypassed."""
        auth_mode = get_auth_mode()
        if auth_mode == "none":
            return None
        if session.get("is_admin", True):
            return None
        if user_db is None:
            return None

        global_settings = load_users_request_policy_settings()
        db_user_id = session.get("db_user_id")
        user_settings: dict[str, Any] | None = None
        if db_user_id is not None:
            try:
                user_settings = user_db.get_user_settings(int(db_user_id))
            except (TypeError, ValueError):
                user_settings = None

        effective = merge_request_policy_settings(global_settings, user_settings)
        if not coerce_bool(effective.get("REQUESTS_ENABLED"), default=False):
            return None

        resolved_mode = resolve_policy_mode(
            source=source,
            content_type=content_type,
            global_settings=global_settings,
            user_settings=user_settings,
        )
        logger.debug(
            "download policy resolve user=%s db_user_id=%s is_admin=%s source=%s content_type=%s mode=%s",
            session.get("user_id"),
            db_user_id,
            bool(session.get("is_admin", False)),
            source,
            content_type,
            resolved_mode.value,
        )
        return resolved_mode

    def _policy_block_response(mode: PolicyMode) -> tuple[Response, int]:
        logger.debug(
            "download policy guard user=%s db_user_id=%s mode=%s",
            session.get("user_id"),
            session.get("db_user_id"),
            mode.value,
        )
        if mode == PolicyMode.BLOCKED:
            return (
                jsonify(
                    {
                        "error": "Download not allowed by policy",
                        "code": "policy_blocked",
                        "required_mode": PolicyMode.BLOCKED.value,
                    }
                ),
                403,
            )
        return (
            jsonify(
                {
                    "error": "Download not allowed by policy",
                    "code": "policy_requires_request",
                    "required_mode": mode.value,
                }
            ),
            403,
        )

    def _resolve_download_user_context(
        db_user_id: Any,
        username: Any,
        on_behalf_of_user_id: Any,
    ) -> tuple[Any, Any, tuple[Response, int] | None]:
        """Resolve download queue user context, including optional admin on-behalf overrides."""
        if on_behalf_of_user_id in (None, ""):
            return db_user_id, username, None

        if not session.get("is_admin", False):
            return db_user_id, username, (jsonify({"error": "Admin required"}), 403)

        if user_db is None:
            return db_user_id, username, (jsonify({"error": "User database unavailable"}), 503)

        try:
            target_user_id = int(on_behalf_of_user_id)
        except (TypeError, ValueError):
            return db_user_id, username, (jsonify({"error": "Invalid on_behalf_of_user_id"}), 400)

        if target_user_id <= 0:
            return db_user_id, username, (jsonify({"error": "Invalid on_behalf_of_user_id"}), 400)

        target_user = user_db.get_user(user_id=target_user_id)
        if not target_user:
            return db_user_id, username, (jsonify({"error": "User not found"}), 404)

        return target_user["id"], target_user["username"], None

    def _resolve_auth_mode_for_routes() -> str:
        """Resolve auth mode lazily so tests and runtime patches still take effect."""
        return get_auth_mode()

    def _queue_release_for_routes(*args: Any, **kwargs: Any) -> Any:
        """Queue a release via the current backend instance."""
        return backend.queue_release(*args, **kwargs)

    def _queue_status_for_routes(user_id: int | None = None) -> dict[str, dict[str, Any]]:
        """Read queue status via the current backend instance."""
        return backend.queue_status(user_id=user_id)

    def _queue_status_to_final_activity_status(status: QueueStatus) -> str | None:
        return status.value if status in TERMINAL_QUEUE_STATUSES else None

    def _queue_status_to_notification_event(status: QueueStatus) -> NotificationEvent | None:
        if status == QueueStatus.COMPLETE:
            return NotificationEvent.DOWNLOAD_COMPLETE
        if status == QueueStatus.ERROR:
            return NotificationEvent.DOWNLOAD_FAILED
        return None

    def _notify_admin_for_terminal_download_status(
        *, task_id: str, status: QueueStatus, task: Any
    ) -> None:
        event = _queue_status_to_notification_event(status)
        if event is None:
            return

        raw_owner_user_id = getattr(task, "user_id", None)
        try:
            owner_user_id = int(raw_owner_user_id) if raw_owner_user_id is not None else None
        except (TypeError, ValueError):
            owner_user_id = None

        content_type = normalize_optional_text(getattr(task, "content_type", None))
        context = NotificationContext(
            event=event,
            title=str(getattr(task, "title", "Unknown title") or "Unknown title"),
            author=str(getattr(task, "author", "Unknown author") or "Unknown author"),
            username=normalize_optional_text(getattr(task, "username", None)),
            content_type=normalize_content_type(content_type) if content_type is not None else None,
            format=normalize_optional_text(getattr(task, "format", None)),
            source=normalize_source(getattr(task, "source", None)),
            error_message=(
                normalize_optional_text(getattr(task, "status_message", None))
                if event == NotificationEvent.DOWNLOAD_FAILED
                else None
            ),
        )
        try:
            notify_admin(event, context)
        except (RuntimeError, TypeError, ValueError) as exc:
            logger.warning(
                "Failed to trigger admin notification for download %s (%s): %s",
                task_id,
                status.value,
                exc,
            )
        if owner_user_id is None:
            return
        try:
            notify_user(owner_user_id, event, context)
        except (RuntimeError, TypeError, ValueError) as exc:
            logger.warning(
                "Failed to trigger user notification for download %s (%s, user_id=%s): %s",
                task_id,
                status.value,
                owner_user_id,
                exc,
            )

    def _emit_activity_update_for_task(*, payload: dict[str, Any], task: Any) -> None:
        owner_user_id = normalize_positive_int(getattr(task, "user_id", None))
        emit_ws_event(
            ws_manager,
            event_name="activity_update",
            room="admins",
            payload=payload,
        )
        if owner_user_id is None:
            return
        emit_ws_event(
            ws_manager,
            event_name="activity_update",
            room=f"user_{owner_user_id}",
            payload=payload,
        )

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

    def _record_download_queued(task_id: str, task: Any) -> None:
        """Persist initial download record when a task enters the queue."""
        if download_history_service is None:
            return

        owner_user_id = normalize_positive_int(getattr(task, "user_id", None))
        request_id = normalize_positive_int(getattr(task, "request_id", None))
        origin = "requested" if request_id else "direct"

        source_name = normalize_source(getattr(task, "source", None))
        source_display = get_source_display_name(source_name)

        try:
            download_history_service.record_download(
                task_id=task_id,
                user_id=owner_user_id,
                username=normalize_optional_text(getattr(task, "username", None)),
                request_id=request_id,
                source=source_name,
                source_display_name=source_display,
                title=str(getattr(task, "title", "Unknown title") or "Unknown title"),
                author=normalize_optional_text(getattr(task, "author", None)),
                file_format=normalize_optional_text(getattr(task, "format", None)),
                size=normalize_optional_text(getattr(task, "size", None)),
                preview=normalize_optional_text(getattr(task, "preview", None)),
                content_type=normalize_optional_text(getattr(task, "content_type", None)),
                origin=origin,
                retry_payload=backend.serialize_task_for_retry(task),
            )
        except _OPERATIONAL_ERRORS as exc:
            logger.warning("Failed to record download at queue time for task %s: %s", task_id, exc)
            return

        if activity_view_state_service is None:
            return

        try:
            cleared_view_state = 0
            cleared_view_state += activity_view_state_service.clear_item_for_all_viewers(
                item_type="download",
                item_key=f"download:{task_id}",
            )
            if request_id is not None:
                cleared_view_state += activity_view_state_service.clear_item_for_all_viewers(
                    item_type="request",
                    item_key=f"request:{request_id}",
                )
            if cleared_view_state > 0:
                _emit_activity_update_for_task(
                    task=task,
                    payload={
                        "kind": "activity_reset",
                        "task_id": task_id,
                    },
                )
        except _OPERATIONAL_ERRORS as exc:
            logger.warning("Failed to reset activity viewer state for task %s: %s", task_id, exc)

    def _record_download_terminal_snapshot(task_id: str, status: QueueStatus, task: Any) -> None:
        _notify_admin_for_terminal_download_status(task_id=task_id, status=status, task=task)

        final_status = _queue_status_to_final_activity_status(status)
        if final_status is None:
            return

        finalized_download = False
        if download_history_service is not None:
            try:
                download_history_service.finalize_download(
                    task_id=task_id,
                    final_status=final_status,
                    status_message=normalize_optional_text(getattr(task, "status_message", None)),
                    download_path=normalize_optional_text(getattr(task, "download_path", None)),
                    retry_payload=backend.serialize_task_for_retry(task),
                )
                finalized_download = True
            except _OPERATIONAL_ERRORS as exc:
                logger.warning("Failed to finalize download history for task %s: %s", task_id, exc)

        if finalized_download:
            _emit_activity_update_for_task(
                task=task,
                payload={
                    "kind": "download_terminal",
                    "task_id": task_id,
                    "status": final_status,
                },
            )

        if user_db is None or status != QueueStatus.ERROR:
            return

        request_id = normalize_positive_int(getattr(task, "request_id", None))
        if request_id is None:
            return
        if backend.can_retry_download_task(task, status):
            return

        raw_error_message = getattr(task, "status_message", None)
        fallback_reason = (
            raw_error_message.strip()
            if isinstance(raw_error_message, str) and raw_error_message.strip()
            else "Download failed"
        )
        try:
            reopened_request = reopen_failed_request(
                user_db,
                request_id=request_id,
                failure_reason=fallback_reason,
            )
            if reopened_request is not None:
                if activity_view_state_service is not None:
                    activity_view_state_service.clear_item_for_all_viewers(
                        item_type="request",
                        item_key=f"request:{request_id}",
                    )
                _emit_request_update_events([reopened_request])
        except _OPERATIONAL_ERRORS as exc:
            logger.warning(
                "Failed to reopen request %s after terminal download error %s: %s",
                request_id,
                task_id,
                exc,
            )

    def _task_owned_by_actor(
        task: Any, *, actor_user_id: int | None, actor_username: str | None
    ) -> bool:
        raw_task_user_id = getattr(task, "user_id", None)
        try:
            task_user_id = int(raw_task_user_id) if raw_task_user_id is not None else None
        except (TypeError, ValueError):
            task_user_id = None

        if actor_user_id is not None and task_user_id is not None:
            return task_user_id == actor_user_id

        task_username = getattr(task, "username", None)
        if isinstance(task_username, str) and task_username.strip() and isinstance(actor_username, str):
            return task_username.strip() == actor_username.strip()

        return False

    def _download_row_owned_by_actor(
        row: dict[str, Any],
        *,
        actor_user_id: int | None,
        actor_username: str | None,
    ) -> bool:
        owner_user_id = normalize_positive_int(row.get("user_id"))
        if actor_user_id is not None and owner_user_id is not None:
            return owner_user_id == actor_user_id

        row_username = normalize_optional_text(row.get("username"))
        if row_username is not None and isinstance(actor_username, str):
            return row_username == actor_username.strip()

        return False

    # Wire orchestrator hooks
    backend.book_queue.set_queue_hook(_record_download_queued)
    backend.book_queue.set_terminal_status_hook(_record_download_terminal_snapshot)

    # -------------------------------------------------------------------------
    # Routes
    # -------------------------------------------------------------------------

    @app.route("/api/releases/download", methods=["POST"])
    @login_required
    def api_download_release() -> Response | tuple[Response, int]:
        """Queue a release for download.

        This endpoint is used when downloading from the ReleaseModal where the
        frontend already has all the release data from the search results.

        Request Body (JSON):
            source (str): Release source (e.g., "direct_download")
            source_id (str): ID within the source (e.g., AA MD5 hash)
            title (str): Book title
            format (str, optional): File format
            size (str, optional): Human-readable size
            extra (dict, optional): Additional metadata

        Returns:
            flask.Response: JSON status object indicating success or failure.

        """
        try:
            data = request.get_json(silent=True)
            if not data:
                return jsonify({"error": "No data provided"}), 400

            if "source_id" not in data:
                return jsonify({"error": "source_id is required"}), 400
            if "source" not in data:
                return jsonify({"error": "source is required"}), 400

            source = data["source"]
            resolved_content_type, inferred_content_type = _resolve_release_content_type(data, source)
            policy_mode = _resolve_policy_mode_for_current_user(
                source=source,
                content_type=resolved_content_type,
            )
            if policy_mode is not None and policy_mode != PolicyMode.DOWNLOAD:
                return _policy_block_response(policy_mode)

            release_payload = data
            if inferred_content_type and data.get("content_type") is None:
                release_payload = dict(data)
                release_payload["content_type"] = resolved_content_type

            priority = data.get("priority", 0)
            # Per-user download overrides
            db_user_id = session.get("db_user_id")
            _username = session.get("user_id")
            db_user_id, _username, on_behalf_error = _resolve_download_user_context(
                db_user_id,
                _username,
                data.get("on_behalf_of_user_id"),
            )
            if on_behalf_error:
                return on_behalf_error
            success, error_msg = backend.queue_release(
                release_payload,
                priority,
                user_id=db_user_id,
                username=_username,
            )

            if success:
                return jsonify({"status": "queued", "priority": priority})
            return jsonify({"error": error_msg or "Failed to queue release"}), 500
        except _OPERATIONAL_ERRORS as e:
            logger.error_trace(f"Release download error: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/status", methods=["GET"])
    @login_required
    def api_status() -> Response | tuple[Response, int]:
        """Get current download queue status.

        Returns:
            flask.Response: JSON object with queue status.

        """
        try:
            is_admin, db_user_id, can_access_status = resolve_status_scope()
            if not can_access_status:
                return jsonify({})

            user_id = None if is_admin else db_user_id
            status = backend.queue_status(user_id=user_id)
            if user_db is not None:
                updated_requests = sync_delivery_states_from_queue_status(
                    user_db,
                    queue_status=status,
                    user_id=user_id,
                )
                _emit_request_update_events(updated_requests)
            return jsonify(status)
        except _OPERATIONAL_ERRORS as e:
            logger.error_trace(f"Status error: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/localdownload", methods=["GET"])
    @login_required
    def api_local_download() -> Response | tuple[Response, int]:
        """Download an EPUB file from local storage if available.

        Query Parameters:
            id (str): Book identifier (MD5 hash)

        Returns:
            flask.Response: The EPUB file if found, otherwise an error response.

        """
        from shelfmark.core.download_history_service import DownloadHistoryService

        book_id = request.args.get("id", "")
        if not book_id:
            return jsonify({"error": "No book ID provided"}), 400

        try:
            file_data, book_info = backend.get_book_data(book_id)
            if file_data is None:
                # Fallback for dismissed/history entries where queue task may no longer exist.
                if download_history_service is not None:
                    is_admin, db_user_id, can_access_status = resolve_status_scope()
                    if can_access_status:
                        history_row = download_history_service.get_by_task_id(book_id)
                        if history_row is not None:
                            owner_user_id = history_row.get("user_id")
                            if is_admin or owner_user_id == db_user_id:
                                download_path = DownloadHistoryService._resolve_existing_download_path(
                                    history_row.get("download_path")
                                )
                                if download_path:
                                    return send_file(
                                        download_path,
                                        download_name=Path(download_path).name,
                                        as_attachment=True,
                                    )

                # Book data not found or not available
                return jsonify({"error": "File not found"}), 404
            file_name = book_info.get_filename() if book_info is not None else Path(book_id).name
            # Prepare the file for sending to the client
            data = io.BytesIO(file_data)
            return send_file(data, download_name=file_name, as_attachment=True)

        except _OPERATIONAL_ERRORS as e:
            logger.error_trace(f"Local download error: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/covers/<cover_id>", methods=["GET"])
    @login_required
    def api_cover(cover_id: str) -> Response | tuple[Response, int]:
        """Serve a cached book cover image.

        This endpoint proxies and caches cover images from external sources.
        Images are cached to disk for faster subsequent requests.

        Path Parameters:
            cover_id (str): Cover identifier (book ID or composite key for universal mode)

        Query Parameters:
            url (str): Base64-encoded original image URL (required on first request)

        Returns:
            flask.Response: Binary image data with appropriate Content-Type, or 404.

        """
        import base64
        import binascii

        try:
            from shelfmark.config.env import is_covers_cache_enabled
            from shelfmark.core.image_cache import get_image_cache

            # Check if caching is enabled
            if not is_covers_cache_enabled():
                return jsonify({"error": "Cover caching is disabled"}), 404

            cache = get_image_cache()

            # Try to get from cache first
            cached = cache.get(cover_id)
            if cached:
                image_data, content_type = cached
                response = app.response_class(response=image_data, status=200, mimetype=content_type)
                response.headers["Cache-Control"] = "public, max-age=86400"
                response.headers["X-Cache"] = "HIT"
                return response

            # Cache miss - get URL from query parameter
            encoded_url = request.args.get("url")
            if not encoded_url:
                return jsonify({"error": "Cover URL not provided"}), 404

            try:
                original_url = base64.urlsafe_b64decode(encoded_url).decode()
            except (binascii.Error, UnicodeDecodeError) as e:
                logger.warning("Failed to decode cover URL: %s", e)
                return jsonify({"error": "Invalid cover URL encoding"}), 400

            # Fetch and cache the image
            result = cache.fetch_and_cache(cover_id, original_url)
            if not result:
                return jsonify({"error": "Failed to fetch cover image"}), 404

            image_data, content_type = result
            response = app.response_class(response=image_data, status=200, mimetype=content_type)
            response.headers["Cache-Control"] = "public, max-age=86400"
            response.headers["X-Cache"] = "MISS"
        except _IMPORT_OPERATIONAL_ERRORS as e:
            logger.error_trace(f"Cover fetch error: {e}")
            return jsonify({"error": str(e)}), 500
        else:
            return response

    @app.route("/api/download/<path:book_id>/cancel", methods=["DELETE"])
    @login_required
    def api_cancel_download(book_id: str) -> Response | tuple[Response, int]:
        """Cancel a download.

        Path Parameters:
            book_id (str): Book identifier to cancel

        Returns:
            flask.Response: JSON status indicating success or failure.

        """
        try:
            task = backend.book_queue.get_task(book_id)
            if task is None:
                return jsonify({"error": "Failed to cancel download or book not found"}), 404

            is_admin, db_user_id, can_access_status = resolve_status_scope()
            if not is_admin:
                if not can_access_status or db_user_id is None:
                    return jsonify(
                        {"error": "User identity unavailable", "code": "user_identity_unavailable"}
                    ), 403

                actor_username = session.get("user_id")
                normalized_actor_username = actor_username if isinstance(actor_username, str) else None
                if not _task_owned_by_actor(
                    task,
                    actor_user_id=db_user_id,
                    actor_username=normalized_actor_username,
                ):
                    return jsonify({"error": "Forbidden", "code": "download_not_owned"}), 403

                if getattr(task, "request_id", None) is not None:
                    return jsonify(
                        {"error": "Forbidden", "code": "requested_download_cancel_forbidden"}
                    ), 403

            success = backend.cancel_download(book_id)
            if success:
                return jsonify({"status": "cancelled", "book_id": book_id})
            return jsonify({"error": "Failed to cancel download or book not found"}), 404
        except _OPERATIONAL_ERRORS as e:
            logger.error_trace(f"Cancel download error: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/download/<path:book_id>/retry", methods=["POST"])
    @login_required
    def api_retry_download(book_id: str) -> Response | tuple[Response, int]:
        """Retry a failed download."""
        try:
            task = backend.book_queue.get_task(book_id)
            history_row = None
            if task is None and download_history_service is not None:
                history_row = download_history_service.get_by_task_id(book_id)
            if task is None and history_row is None:
                return jsonify({"error": "Download not found"}), 404

            is_admin, db_user_id, can_access_status = resolve_status_scope()
            actor_username = session.get("user_id")
            normalized_actor_username = actor_username if isinstance(actor_username, str) else None
            if not is_admin:
                if not can_access_status or db_user_id is None:
                    return jsonify(
                        {"error": "User identity unavailable", "code": "user_identity_unavailable"}
                    ), 403

                if task is not None:
                    if not _task_owned_by_actor(
                        task,
                        actor_user_id=db_user_id,
                        actor_username=normalized_actor_username,
                    ):
                        return jsonify({"error": "Forbidden", "code": "download_not_owned"}), 403
                elif history_row is None or not _download_row_owned_by_actor(
                    history_row,
                    actor_user_id=db_user_id,
                    actor_username=normalized_actor_username,
                ):
                    return jsonify({"error": "Forbidden", "code": "download_not_owned"}), 403

            if task is not None:
                task_status = backend.book_queue.get_task_status(book_id)
                if getattr(
                    task, "request_id", None
                ) is not None and not backend.can_retry_download_task(task, task_status):
                    return jsonify(
                        {"error": "Forbidden", "code": "requested_download_retry_forbidden"}
                    ), 403
                success, error = backend.retry_download(book_id)
            else:
                if history_row is None:
                    logger.error("Download history row disappeared while retrying task %s", book_id)
                    return jsonify({"error": "Download history not found"}), 404
                request_id = normalize_positive_int(history_row.get("request_id"))
                retry_payload = history_row.get("retry_payload")
                final_status = history_row.get("final_status")
                if request_id is not None:
                    history_service = download_history_service
                    if history_service is None:
                        logger.error(
                            "Download history service unavailable while retrying task %s", book_id
                        )
                        return jsonify({"error": "Download history unavailable"}), 500
                    if not history_service.is_retry_available(history_row):
                        return jsonify(
                            {"error": "Forbidden", "code": "requested_download_retry_forbidden"}
                        ), 403
                success, error = backend.retry_persisted_download(
                    retry_payload,
                    final_status=final_status,
                )

            if success:
                return jsonify({"status": "queued", "book_id": book_id})

            if error == "Download not found":
                return jsonify({"error": error}), 404

            return jsonify({"error": error or "Download cannot be retried"}), 409
        except _OPERATIONAL_ERRORS as e:
            logger.error_trace(f"Retry download error: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/queue/<path:book_id>/priority", methods=["PUT"])
    @login_required
    def api_set_priority(book_id: str) -> Response | tuple[Response, int]:
        """Set priority for a queued book.

        Path Parameters:
            book_id (str): Book identifier

        Request Body:
            priority (int): New priority level (lower number = higher priority)

        Returns:
            flask.Response: JSON status indicating success or failure.

        """
        try:
            data = request.get_json(silent=True)
            if not data or "priority" not in data:
                return jsonify({"error": "Priority not provided"}), 400

            priority = int(data["priority"])
            success = backend.set_book_priority(book_id, priority)

            if success:
                return jsonify({"status": "updated", "book_id": book_id, "priority": priority})
            return jsonify({"error": "Failed to update priority or book not found"}), 404
        except ValueError:
            return jsonify({"error": "Invalid priority value"}), 400
        except _OPERATIONAL_ERRORS as e:
            logger.error_trace(f"Set priority error: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/queue/reorder", methods=["POST"])
    @login_required
    def api_reorder_queue() -> Response | tuple[Response, int]:
        """Bulk reorder queue by setting new priorities.

        Request Body:
            book_priorities (dict): Mapping of book_id to new priority

        Returns:
            flask.Response: JSON status indicating success or failure.

        """
        try:
            data = request.get_json(silent=True)
            if not data or "book_priorities" not in data:
                return jsonify({"error": "book_priorities not provided"}), 400

            book_priorities = data["book_priorities"]
            if not isinstance(book_priorities, dict):
                return jsonify({"error": "book_priorities must be a dictionary"}), 400

            # Validate all priorities are integers
            for book_id, priority in book_priorities.items():
                if not isinstance(priority, int):
                    return jsonify({"error": f"Invalid priority for book {book_id}"}), 400

            success = backend.reorder_queue(book_priorities)

            if success:
                return jsonify({"status": "reordered", "updated_count": len(book_priorities)})
            return jsonify({"error": "Failed to reorder queue"}), 500
        except _OPERATIONAL_ERRORS as e:
            logger.error_trace(f"Reorder queue error: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/queue/order", methods=["GET"])
    @login_required
    def api_queue_order() -> Response | tuple[Response, int]:
        """Get current queue order for display.

        Returns:
            flask.Response: JSON array of queued books with their order and priorities.

        """
        try:
            queue_order = backend.get_queue_order()
            return jsonify({"queue": queue_order})
        except _OPERATIONAL_ERRORS as e:
            logger.error_trace(f"Queue order error: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/downloads/active", methods=["GET"])
    @login_required
    def api_active_downloads() -> Response | tuple[Response, int]:
        """Get list of currently active downloads.

        Returns:
            flask.Response: JSON array of active download book IDs.

        """
        try:
            active_downloads = backend.get_active_downloads()
            return jsonify({"active_downloads": active_downloads})
        except _OPERATIONAL_ERRORS as e:
            logger.error_trace(f"Active downloads error: {e}")
            return jsonify({"error": str(e)}), 500
