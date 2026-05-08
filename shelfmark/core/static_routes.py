"""Static asset and frontend routes.

Registers routes that serve the built React frontend, including the catch-all
for React Router client-side navigation and optional debug/restart endpoints.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from flask import Flask, Response, jsonify, send_file, send_from_directory

from shelfmark.core.auth_middleware import login_required
from shelfmark.core.logger import setup_logger

if TYPE_CHECKING:
    pass

logger = setup_logger(__name__)

_OPERATIONAL_ERRORS = (OSError, RuntimeError, TypeError, ValueError, sqlite3.Error)
_IMPORT_OPERATIONAL_ERRORS = (ImportError, *_OPERATIONAL_ERRORS)

_BASE_TAG = '<base href="/" data-shelfmark-base />'


def register_static_routes(app: Flask, frontend_dist: Path, base_path: str) -> None:
    """Register static asset and frontend serving routes on the Flask app."""

    def _base_href() -> str:
        if not base_path:
            return "/"
        return f"{base_path}/"

    def _serve_index_html() -> Response:
        """Serve index.html with an adjusted base tag for subpath deployments."""
        index_path = frontend_dist / "index.html"
        try:
            with index_path.open(encoding="utf-8") as handle:
                html = handle.read()
        except OSError:
            return send_from_directory(frontend_dist, "index.html")

        if base_path and _BASE_TAG in html:
            html = html.replace(_BASE_TAG, f'<base href="{_base_href()}" data-shelfmark-base />', 1)

        return Response(html, mimetype="text/html")

    # Serve frontend static files
    @app.route("/assets/<path:filename>")
    def serve_frontend_assets(filename: str) -> Response:
        """Serve static assets from the built frontend."""
        return send_from_directory(frontend_dist / "assets", filename)

    @app.route("/")
    def index() -> Response:
        """Serve the React frontend application.

        Authentication is handled by the React app itself.
        """
        return _serve_index_html()

    @app.route("/theme-init.js")
    def theme_init_js() -> Response:
        """Serve the blocking theme-init script."""
        return send_from_directory(frontend_dist, "theme-init.js", mimetype="application/javascript")

    @app.route("/logo.png")
    def logo() -> Response:
        """Serve logo from built frontend assets."""
        return send_from_directory(frontend_dist, "logo.png", mimetype="image/png")

    @app.route("/favicon.ico")
    @app.route("/favico<path:_>")
    def favicon(_: Any = None) -> Response:
        """Serve favicon from built frontend assets."""
        return send_from_directory(frontend_dist, "favicon.ico", mimetype="image/vnd.microsoft.icon")

    # Catch-all route for React Router (must be last)
    # This handles client-side routing by serving index.html for any unmatched routes
    @app.route("/<path:path>")
    def catch_all(path: str) -> Response | tuple[Response, int]:
        """Serve the React app for any route not matched by API endpoints.

        This allows React Router to handle client-side routing.
        Authentication is handled by the React app itself.
        """
        # If the request is for an API endpoint or static file, let it 404
        if path.startswith(("api/", "assets/")):
            return jsonify({"error": "Resource not found"}), 404
        # Otherwise serve the React app
        return _serve_index_html()


def register_debug_routes(app: Flask, is_debug_enabled: bool) -> None:
    """Register debug/restart routes when debug mode is enabled."""
    if not is_debug_enabled:
        return

    import subprocess

    from shelfmark.core.config import config as app_config
    from shelfmark.core.utils import normalize_base_path  # noqa: F401

    def _stop_gui() -> None:
        return None

    if app_config.get("USING_EXTERNAL_BYPASSER", False):
        pass
    else:
        from shelfmark.bypass.internal_bypasser import _cleanup_orphan_processes

        def _stop_gui() -> None:  # type: ignore[misc]
            _cleanup_orphan_processes()

    @app.route("/api/debug", methods=["GET"])
    @login_required
    def debug() -> Response | tuple[Response, int]:
        """Run `/app/genDebug.sh`, generate a debug zip, and return it.

        The file is written to `/tmp/shelfmark-debug.zip` before being returned.
        """
        try:
            logger.info("Debug endpoint called, stopping GUI and generating debug info...")
            _stop_gui()
            time.sleep(1)
            result = subprocess.run(
                ["/app/genDebug.sh"], capture_output=True, text=True, check=True
            )
            if result.returncode != 0:
                raise RuntimeError(f"Debug script failed: {result.stderr}")
            logger.info("Debug script executed: %s", result.stdout)
            debug_file_path = result.stdout.strip().split("\n")[-1]
            if not Path(debug_file_path).exists():
                logger.error("Debug zip file not found at: %s", debug_file_path)
                return jsonify({"error": "Failed to generate debug information"}), 500

            logger.info("Sending debug file: %s", debug_file_path)
            return send_file(
                debug_file_path,
                mimetype="application/zip",
                download_name=Path(debug_file_path).name,
                as_attachment=True,
            )
        except subprocess.CalledProcessError as e:
            logger.error_trace(f"Debug script error: {e}, stdout: {e.stdout}, stderr: {e.stderr}")
            return jsonify({"error": f"Debug script failed: {e.stderr}"}), 500
        except _OPERATIONAL_ERRORS as e:
            logger.error_trace(f"Debug endpoint error: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/restart", methods=["GET"])
    @login_required
    def restart() -> Response | tuple[Response, int]:
        """Restart the application."""
        os._exit(0)
