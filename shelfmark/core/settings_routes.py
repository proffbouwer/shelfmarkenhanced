"""Settings and onboarding API routes.

Registers /api/settings/* and /api/onboarding/* endpoints for reading and
writing application configuration through the settings registry.
"""

from __future__ import annotations

import sqlite3

from flask import Flask, Response, jsonify, request

from shelfmark.core.auth_middleware import login_required
from shelfmark.core.logger import setup_logger

logger = setup_logger(__name__)

_OPERATIONAL_ERRORS = (OSError, RuntimeError, TypeError, ValueError, sqlite3.Error)
_IMPORT_OPERATIONAL_ERRORS = (ImportError, *_OPERATIONAL_ERRORS)


def register_settings_routes(app: Flask) -> None:
    """Register settings and onboarding routes on the Flask app."""

    @app.route("/api/settings", methods=["GET"])
    @login_required
    def api_settings_get_all() -> Response | tuple[Response, int]:
        """Get all settings tabs with their fields and current values.

        Returns:
            flask.Response: JSON with all settings tabs.

        """
        try:
            from shelfmark.core.settings_registry import serialize_all_settings

            data = serialize_all_settings(include_values=True)
            return jsonify(data)
        except _IMPORT_OPERATIONAL_ERRORS as e:
            logger.error_trace(f"Settings get error: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/settings/<tab_name>", methods=["GET"])
    @login_required
    def api_settings_get_tab(tab_name: str) -> Response | tuple[Response, int]:
        """Get settings for a specific tab.

        Path Parameters:
            tab_name (str): Settings tab name (e.g., "general", "hardcover")

        Returns:
            flask.Response: JSON with tab settings and values.

        """
        try:
            from shelfmark.core.settings_registry import get_settings_tab, serialize_tab

            tab = get_settings_tab(tab_name)
            if not tab:
                return jsonify({"error": f"Unknown settings tab: {tab_name}"}), 404

            return jsonify(serialize_tab(tab, include_values=True))
        except _IMPORT_OPERATIONAL_ERRORS as e:
            logger.error_trace(f"Settings get tab error: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/settings/<tab_name>", methods=["PUT"])
    @login_required
    def api_settings_update_tab(tab_name: str) -> Response | tuple[Response, int]:
        """Update settings for a specific tab.

        Path Parameters:
            tab_name (str): Settings tab name

        Request Body:
            JSON object with setting keys and values to update.

        Returns:
            flask.Response: JSON with update result.

        """
        try:
            from shelfmark.core.settings_registry import get_settings_tab, update_settings

            tab = get_settings_tab(tab_name)
            if not tab:
                return jsonify({"error": f"Unknown settings tab: {tab_name}"}), 404

            values = request.get_json(silent=True)
            if values is None or not isinstance(values, dict):
                return jsonify({"error": "Request body must be a JSON object"}), 400

            if not values:
                return jsonify({"success": True, "message": "No changes to save", "updated": []})

            result = update_settings(tab_name, values)

            if result["success"]:
                return jsonify(result)
            return jsonify(result), 400
        except _IMPORT_OPERATIONAL_ERRORS as e:
            logger.error_trace(f"Settings update error: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/settings/<tab_name>/action/<action_key>", methods=["POST"])
    @login_required
    def api_settings_execute_action(tab_name: str, action_key: str) -> Response | tuple[Response, int]:
        """Execute a settings action (e.g., test connection).

        Path Parameters:
            tab_name (str): Settings tab name
            action_key (str): Action key to execute

        Request Body (optional):
            JSON object with current form values (unsaved)

        Returns:
            flask.Response: JSON with action result.

        """
        try:
            from shelfmark.core.settings_registry import execute_action

            current_values = request.get_json(silent=True) or {}
            result = execute_action(tab_name, action_key, current_values)

            if result["success"]:
                return jsonify(result)
            return jsonify(result), 400
        except _IMPORT_OPERATIONAL_ERRORS as e:
            logger.error_trace(f"Settings action error: {e}")
            return jsonify({"error": str(e)}), 500

    # =============================================================================
    # Onboarding API
    # =============================================================================

    @app.route("/api/onboarding", methods=["GET"])
    @login_required
    def api_onboarding_get() -> Response | tuple[Response, int]:
        """Get onboarding configuration including steps, fields, and current values.

        Returns:
            flask.Response: JSON with onboarding steps and values.

        """
        try:
            from shelfmark.core.onboarding import get_onboarding_config

            config = get_onboarding_config()
            return jsonify(config)
        except _IMPORT_OPERATIONAL_ERRORS as e:
            logger.error_trace(f"Onboarding get error: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/onboarding", methods=["POST"])
    @login_required
    def api_onboarding_save() -> Response | tuple[Response, int]:
        """Save onboarding settings and mark as complete.

        Request Body:
            JSON object with all onboarding field values

        Returns:
            flask.Response: JSON with success/error status.

        """
        try:
            from shelfmark.core.onboarding import save_onboarding_settings

            data = request.get_json(silent=True)
            if not data:
                return jsonify({"success": False, "message": "No data provided"}), 400

            result = save_onboarding_settings(data)

            if result["success"]:
                return jsonify(result)
            return jsonify(result), 400
        except _IMPORT_OPERATIONAL_ERRORS as e:
            logger.error_trace(f"Onboarding save error: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/onboarding/skip", methods=["POST"])
    @login_required
    def api_onboarding_skip() -> Response | tuple[Response, int]:
        """Skip onboarding and mark as complete without saving any settings.

        Returns:
            flask.Response: JSON with success status.

        """
        try:
            from shelfmark.core.onboarding import mark_onboarding_complete

            mark_onboarding_complete()
            return jsonify({"success": True, "message": "Onboarding skipped"})
        except _IMPORT_OPERATIONAL_ERRORS as e:
            logger.error_trace(f"Onboarding skip error: {e}")
            return jsonify({"error": str(e)}), 500
