"""Library routes — browse completed downloads, re-deliver or delete files.

Endpoints
---------
GET  /api/library                          — paginated list of completed downloads
POST /api/library/<task_id>/send-to-acw    — push file to Automatic Calibre Web
POST /api/library/<task_id>/send-to-folder — copy file to an arbitrary folder
DELETE /api/library/<task_id>             — remove file + history row
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any

from flask import jsonify, request

from shelfmark.core.api_errors import handle_api_errors
from shelfmark.core.auth_middleware import login_required, resolve_status_scope
from shelfmark.core.logger import setup_logger
from shelfmark.core.request_helpers import normalize_optional_positive_int, normalize_optional_text

if TYPE_CHECKING:
    from flask import Flask, Response

    from shelfmark.core.download_history_service import DownloadHistoryService

logger = setup_logger(__name__)

_LIBRARY_PAGE_SIZE_DEFAULT = 50
_LIBRARY_PAGE_SIZE_MAX = 200


def _clamp_int(value: object, *, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


def register_library_routes(
    app: Flask,
    download_history_service: DownloadHistoryService,
) -> None:
    """Register /api/library/* routes on *app*."""

    # ------------------------------------------------------------------
    # GET /api/library
    # ------------------------------------------------------------------
    @app.route("/api/library", methods=["GET"])
    @login_required
    @handle_api_errors("library list")
    def api_library_list() -> Response | tuple[Response, int]:
        """Return a paginated list of completed downloads visible to the caller.

        Query params:
            page        int  (default 1)
            page_size   int  (default 50, max 200)
            visibility  str  "all" | "public" | "private"  (default "all")
            q           str  free-text search on title/author
            final_status str "complete" | "error" | "cancelled" (default all terminal)
        """
        is_admin, db_user_id, can_access = resolve_status_scope()
        if not can_access:
            return jsonify({"items": [], "total": 0, "page": 1, "page_size": _LIBRARY_PAGE_SIZE_DEFAULT}), 200

        page = _clamp_int(request.args.get("page", 1), default=1, minimum=1, maximum=10_000)
        page_size = _clamp_int(
            request.args.get("page_size", _LIBRARY_PAGE_SIZE_DEFAULT),
            default=_LIBRARY_PAGE_SIZE_DEFAULT,
            minimum=1,
            maximum=_LIBRARY_PAGE_SIZE_MAX,
        )
        vis_filter = normalize_optional_text(request.args.get("visibility")) or "all"
        q = normalize_optional_text(request.args.get("q"))
        status_filter = normalize_optional_text(request.args.get("final_status"))

        rows, total = download_history_service.list_library(
            is_admin=is_admin,
            db_user_id=db_user_id,
            page=page,
            page_size=page_size,
            visibility=vis_filter,
            search_query=q,
            final_status=status_filter,
        )

        items = [_row_to_library_item(r) for r in rows]
        return jsonify({"items": items, "total": total, "page": page, "page_size": page_size})

    # ------------------------------------------------------------------
    # POST /api/library/<task_id>/send-to-acw
    # ------------------------------------------------------------------
    @app.route("/api/library/<task_id>/send-to-acw", methods=["POST"])
    @login_required
    @handle_api_errors("library send-to-acw")
    def api_library_send_to_acw(task_id: str) -> Response | tuple[Response, int]:
        """Copy a completed download's file into the Calibre Web ingest folder.

        The target ingest path is read from the CALIBRE_WEB_INGEST_DIR setting
        (falls back to ACW_IMPORT_DIR, then /acw-book-ingest).
        """
        from shelfmark.core.config import config

        row, error_response = _resolve_library_row(task_id, download_history_service)
        if error_response:
            return error_response

        assert row is not None
        download_path = row.get("download_path")
        if not download_path or not Path(download_path).exists():
            return jsonify({"error": "File not found on disk"}), 404

        acw_ingest = (
            normalize_optional_text(config.get("CALIBRE_WEB_INGEST_DIR", ""))
            or normalize_optional_text(config.get("ACW_IMPORT_DIR", ""))
            or "/acw-book-ingest"
        )
        dest_dir = Path(acw_ingest)
        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_file = dest_dir / Path(download_path).name
            shutil.copy2(download_path, dest_file)
        except OSError as exc:
            logger.warning("send-to-acw failed for %s: %s", task_id, exc)
            return jsonify({"error": f"Failed to copy file: {exc}"}), 500

        logger.info("Library: copied %s → %s (ACW ingest)", download_path, dest_file)
        return jsonify({"status": "ok", "dest": str(dest_file)})

    # ------------------------------------------------------------------
    # POST /api/library/<task_id>/send-to-folder
    # ------------------------------------------------------------------
    @app.route("/api/library/<task_id>/send-to-folder", methods=["POST"])
    @login_required
    @handle_api_errors("library send-to-folder")
    def api_library_send_to_folder(task_id: str) -> Response | tuple[Response, int]:
        """Copy a completed download's file to an arbitrary destination folder.

        Request body (JSON):
            folder  str  — absolute destination directory path (required)
        """
        data = request.get_json(silent=True) or {}
        dest_folder = normalize_optional_text(data.get("folder"))
        if not dest_folder:
            return jsonify({"error": "folder is required"}), 400

        dest_dir = Path(dest_folder)
        if not dest_dir.is_absolute():
            return jsonify({"error": "folder must be an absolute path"}), 400

        row, error_response = _resolve_library_row(task_id, download_history_service)
        if error_response:
            return error_response

        assert row is not None
        download_path = row.get("download_path")
        if not download_path or not Path(download_path).exists():
            return jsonify({"error": "File not found on disk"}), 404

        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_file = dest_dir / Path(download_path).name
            shutil.copy2(download_path, dest_file)
        except OSError as exc:
            logger.warning("send-to-folder failed for %s: %s", task_id, exc)
            return jsonify({"error": f"Failed to copy file: {exc}"}), 500

        logger.info("Library: copied %s → %s", download_path, dest_file)
        return jsonify({"status": "ok", "dest": str(dest_file)})

    # ------------------------------------------------------------------
    # DELETE /api/library/<task_id>
    # ------------------------------------------------------------------
    @app.route("/api/library/<task_id>", methods=["DELETE"])
    @login_required
    @handle_api_errors("library delete")
    def api_library_delete(task_id: str) -> Response | tuple[Response, int]:
        """Delete the file from disk and remove the download_history row."""
        row, error_response = _resolve_library_row(task_id, download_history_service)
        if error_response:
            return error_response

        assert row is not None
        download_path = row.get("download_path")
        deleted_file = False
        if download_path:
            file_path = Path(download_path)
            if file_path.exists():
                try:
                    file_path.unlink()
                    deleted_file = True
                except OSError as exc:
                    logger.warning("Library: failed to delete file %s: %s", download_path, exc)

        download_history_service.delete_by_task_id(task_id)
        return jsonify({"status": "ok", "deleted_file": deleted_file})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row_to_library_item(row: dict[str, Any]) -> dict[str, Any]:
    """Serialize a download_history row to a library API item."""
    return {
        "task_id": row.get("task_id"),
        "title": row.get("title"),
        "author": row.get("author"),
        "format": row.get("format"),
        "size": row.get("size"),
        "preview": row.get("preview"),
        "content_type": row.get("content_type"),
        "source": row.get("source"),
        "source_display_name": row.get("source_display_name"),
        "visibility": row.get("visibility", "public"),
        "final_status": row.get("final_status"),
        "download_path": row.get("download_path"),
        "file_exists": bool(row.get("download_path") and Path(str(row["download_path"])).exists()),
        "user_id": row.get("user_id"),
        "username": row.get("username"),
        "queued_at": row.get("queued_at"),
        "terminal_at": row.get("terminal_at"),
        "request_id": row.get("request_id"),
    }


def _resolve_library_row(
    task_id: str,
    svc: DownloadHistoryService,
) -> tuple[dict[str, Any] | None, tuple[Any, int] | None]:
    """Look up the row, enforcing ownership for private downloads.

    Returns (row, None) on success or (None, error_response) on failure.
    """
    is_admin, db_user_id, can_access = resolve_status_scope()
    if not can_access:
        return None, (jsonify({"error": "Unauthorized"}), 403)

    row = svc.get_by_task_id(task_id)
    if row is None:
        return None, (jsonify({"error": "Not found"}), 404)

    owner_user_id = normalize_optional_positive_int(row.get("user_id"), "user_id")
    row_visibility = row.get("visibility", "public")

    if row_visibility == "private" and not is_admin and owner_user_id != db_user_id:
        return None, (jsonify({"error": "Access denied"}), 403)

    return row, None
