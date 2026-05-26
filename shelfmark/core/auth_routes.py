"""Authentication routes and request/response middleware.

Registers /api/auth/* endpoints (login, logout, auth check) together with the
proxy-auth before_request middleware and the security-headers after_request hook.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from flask import Flask, Response, jsonify, request, session
from werkzeug.security import check_password_hash

from shelfmark.config.env import CWA_DB_PATH, HIDE_LOCAL_AUTH, OIDC_AUTO_REDIRECT
from shelfmark.core.auth_middleware import get_auth_mode, get_client_ip, login_required
from shelfmark.core.auth_modes import get_auth_check_admin_status
from shelfmark.core.config import config as app_config
from shelfmark.core.cwa_user_sync import upsert_cwa_user
from shelfmark.core.external_user_linking import upsert_external_user
from shelfmark.core.logger import setup_logger
from shelfmark.core.rate_limit import (
    LOCKOUT_DURATION_MINUTES,
    LOGIN_ATTEMPT_WARNING_THRESHOLD,
    MAX_LOGIN_ATTEMPTS,
    clear_failed_logins,
    get_attempt_count,
    get_lockout_remaining_minutes,
    is_account_locked,
    record_failed_login,
)
from shelfmark.core.request_helpers import normalize_optional_text

if TYPE_CHECKING:
    from shelfmark.core.user_db import UserDB

logger = setup_logger(__name__)

_OPERATIONAL_ERRORS = (OSError, RuntimeError, TypeError, ValueError, sqlite3.Error)
_IMPORT_OPERATIONAL_ERRORS = (ImportError, *_OPERATIONAL_ERRORS)


def register_auth_routes(app: Flask, user_db: UserDB | None, user_db_path: str) -> None:
    """Register authentication routes and middleware on the Flask app."""

    def proxy_auth_middleware() -> Response | tuple[Response, int] | None:
        """Middleware to handle proxy authentication.

        When AUTH_METHOD is set to "proxy", this middleware automatically
        authenticates users based on headers set by the reverse proxy.
        """
        auth_mode = get_auth_mode()

        # Only run for proxy auth mode
        if auth_mode != "proxy":
            return None

        # Skip for public endpoints that don't need auth
        if request.path == "/api/health":
            return None

        def get_proxy_header(header_name: str) -> str | None:
            """Resolve proxy auth values from headers with WSGI env fallbacks."""
            value = request.headers.get(header_name)
            if value:
                return value

            env_key = f"HTTP_{header_name.upper().replace('-', '_')}"
            value = request.environ.get(env_key)
            if value:
                return value

            # Some proxies set authenticated username in REMOTE_USER (not as a header).
            if header_name.lower().replace("_", "-") == "remote-user":
                return request.environ.get("REMOTE_USER")

            return None

        try:
            user_header = (
                normalize_optional_text(app_config.get("PROXY_AUTH_USER_HEADER", "X-Auth-User"))
                or "X-Auth-User"
            )

            # Extract username from proxy header
            username = get_proxy_header(user_header)

            if not username:
                if request.path.startswith("/api/auth/"):
                    return None

                logger.warning("Proxy auth enabled but no username found in header '%s'", user_header)
                return jsonify({"error": "Authentication required. Proxy header not set."}), 401

            # Resolve admin role for proxy sessions.
            # If an admin group is configured, derive from groups header.
            # Otherwise preserve existing DB role for known users and default
            # first-time users to admin (to avoid lockouts).
            admin_group_header = (
                normalize_optional_text(
                    app_config.get("PROXY_AUTH_ADMIN_GROUP_HEADER", "X-Auth-Groups")
                )
                or "X-Auth-Groups"
            )
            admin_group_name = (
                normalize_optional_text(app_config.get("PROXY_AUTH_ADMIN_GROUP_NAME", "")) or ""
            )
            is_admin = True

            if admin_group_name:
                groups_header = get_proxy_header(admin_group_header) or ""
                user_groups_delimiter = "," if "," in groups_header else "|"
                user_groups = [
                    g.strip() for g in groups_header.split(user_groups_delimiter) if g.strip()
                ]
                is_admin = admin_group_name in user_groups
            elif user_db is not None:
                existing_db_user = user_db.get_user(username=username)
                if existing_db_user:
                    is_admin = existing_db_user.get("role") == "admin"

            # Create or update session
            previous_username = session.get("user_id")
            if previous_username and previous_username != username:
                # Header identity changed mid-session; force reprovision for the new user.
                session.pop("db_user_id", None)

            session["user_id"] = username
            session["is_admin"] = is_admin

            # Provision proxy-authenticated users into users.db for multi-user features.
            # Re-provision when db_user_id is missing/stale/mismatched to avoid broken
            # sessions after DB resets or auth-mode transitions.
            if user_db is not None:
                raw_db_user_id = session.get("db_user_id")
                session_db_user = None

                if raw_db_user_id is not None:
                    try:
                        session_db_user = user_db.get_user(user_id=int(raw_db_user_id))
                    except (TypeError, ValueError):
                        session_db_user = None

                session_db_username = (
                    str(session_db_user.get("username") or "").strip() if session_db_user else ""
                )
                needs_db_user_sync = (
                    raw_db_user_id is None or session_db_user is None or session_db_username != username
                )

                if needs_db_user_sync:
                    role = "admin" if is_admin else "user"
                    db_user, _ = upsert_external_user(
                        user_db,
                        auth_source="proxy",
                        username=username,
                        role=role,
                        collision_strategy="takeover",
                        context="proxy_request",
                    )
                    if db_user is None:
                        raise RuntimeError("Unexpected proxy user sync result: no user returned")

                    session["db_user_id"] = db_user["id"]

            session.permanent = False
        except _OPERATIONAL_ERRORS:
            logger.exception("Proxy auth middleware error")
            return jsonify({"error": "Authentication error"}), 500
        else:
            return None

    def set_security_headers(response: Response) -> Response:
        """Add baseline security headers to every response."""
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: https://images.unsplash.com https://covers.openlibrary.org https://hardcover.app https://*.cloudfront.net; font-src 'self' https://cdn.jsdelivr.net; connect-src 'self' ws: wss:",
        )
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault("Cross-Origin-Embedder-Policy", "credentialless")
        return response

    app.before_request(proxy_auth_middleware)
    app.after_request(set_security_headers)

    def _failed_login_response(username: str, ip_address: str) -> tuple[Response, int]:
        """Handle a failed login attempt by recording it and returning the appropriate response."""
        is_now_locked = record_failed_login(user_db_path, username, ip_address)

        if is_now_locked:
            return jsonify(
                {
                    "error": f"Account locked due to {MAX_LOGIN_ATTEMPTS} failed login attempts. Try again in {LOCKOUT_DURATION_MINUTES} minutes."
                }
            ), 429

        count = get_attempt_count(user_db_path, username)
        attempts_remaining = MAX_LOGIN_ATTEMPTS - count
        if attempts_remaining <= LOGIN_ATTEMPT_WARNING_THRESHOLD:
            return jsonify(
                {"error": f"Invalid username or password. {attempts_remaining} attempts remaining."}
            ), 401

        return jsonify({"error": "Invalid username or password."}), 401

    @app.route("/api/auth/login", methods=["POST"])
    def api_login() -> Response | tuple[Response, int]:
        """Login endpoint that validates credentials and creates a session.

        Supports both built-in credentials and CWA database authentication.
        Includes rate limiting: 10 failed attempts = 30 minute lockout.

        Request Body:
            username (str): Username
            password (str): Password
            remember_me (bool): Whether to extend session duration

        Returns:
            flask.Response: JSON with success status or error message.

        """
        try:
            ip_address = get_client_ip()
            data = request.get_json(silent=True)
            if not data:
                return jsonify({"error": "No data provided"}), 400

            auth_mode = get_auth_mode()
            if auth_mode == "proxy":
                return jsonify({"error": "Proxy authentication is enabled"}), 401

            if auth_mode == "oidc" and HIDE_LOCAL_AUTH:
                return jsonify({"error": "Local authentication is disabled"}), 403

            username = data.get("username", "").strip()
            password = data.get("password", "")
            remember_me = data.get("remember_me", False)

            if not username or not password:
                return jsonify({"error": "Username and password are required"}), 400

            # Check if account is locked due to failed login attempts
            if is_account_locked(user_db_path, username):
                remaining_minutes = get_lockout_remaining_minutes(user_db_path, username)
                wait_str = f"{remaining_minutes} minutes" if remaining_minutes else f"{LOCKOUT_DURATION_MINUTES} minutes"
                logger.warning(
                    "Login attempt blocked for locked account '%s' from IP %s", username, ip_address
                )
                return jsonify(
                    {
                        "error": f"Account temporarily locked due to multiple failed login attempts. Try again in {wait_str}."
                    }
                ), 429

            # If no authentication is configured, authentication always succeeds
            if auth_mode == "none":
                session["user_id"] = username
                session.permanent = remember_me
                clear_failed_logins(user_db_path, username)
                logger.info(
                    "Login successful for user '%s' from IP %s (no auth configured)",
                    username,
                    ip_address,
                )
                return jsonify({"success": True})

            # Password authentication (builtin and OIDC modes)
            # OIDC mode also allows password login as a fallback so admins don't get locked out
            if auth_mode in ("builtin", "oidc"):
                if user_db is None:
                    logger.error("User database not available for %s auth", auth_mode)
                    return jsonify({"error": "Authentication service unavailable"}), 503
                try:
                    db_user = user_db.get_user(username=username)

                    if not db_user:
                        return _failed_login_response(username, ip_address)

                    # Authenticate against DB user
                    if db_user:
                        if not db_user.get("password_hash") or not check_password_hash(
                            db_user["password_hash"], password
                        ):
                            return _failed_login_response(username, ip_address)

                        is_admin = db_user["role"] == "admin"
                        session["user_id"] = username
                        session["db_user_id"] = db_user["id"]
                        session["is_admin"] = is_admin
                        session["login_at"] = datetime.now(UTC).isoformat()
                        session.permanent = remember_me
                        clear_failed_logins(user_db_path, username)
                        user_db.record_login(db_user["id"])
                        logger.info(
                            "Login successful for user '%s' from IP %s (%s auth, is_admin=%s, remember_me=%s)",
                            username,
                            ip_address,
                            auth_mode,
                            is_admin,
                            remember_me,
                        )
                        return jsonify({"success": True})

                    return _failed_login_response(username, ip_address)

                except _OPERATIONAL_ERRORS as e:
                    logger.error_trace(f"Built-in auth error: {e}")
                    return jsonify({"error": "Authentication system error"}), 500

            # CWA database authentication mode
            if auth_mode == "cwa":
                # Verify database still exists (it was validated at startup)
                if not CWA_DB_PATH or not CWA_DB_PATH.exists():
                    logger.error("CWA database at %s is no longer accessible", CWA_DB_PATH)
                    return jsonify({"error": "Database configuration error"}), 500

                try:
                    import os

                    db_path = os.fspath(CWA_DB_PATH)
                    db_uri = f"file:{db_path}?mode=ro&immutable=1"
                    conn = sqlite3.connect(db_uri, uri=True)
                    cur = conn.cursor()
                    cur.execute("SELECT password, role, email FROM user WHERE name = ?", (username,))
                    row = cur.fetchone()
                    conn.close()

                    # Check if user exists and password is correct
                    if not row or not row[0] or not check_password_hash(row[0], password):
                        return _failed_login_response(username, ip_address)

                    # Check if user has admin role (ROLE_ADMIN = 1, bit flag)
                    user_role = row[1] if row[1] is not None else 0
                    is_admin = (user_role & 1) == 1
                    cwa_email = row[2] or None

                    db_user_id = None
                    if user_db is not None:
                        role = "admin" if is_admin else "user"
                        db_user, _ = upsert_cwa_user(
                            user_db,
                            cwa_username=username,
                            cwa_email=cwa_email,
                            role=role,
                            context="cwa_login",
                        )
                        db_user_id = db_user["id"]

                    # Successful authentication - create session and clear failed attempts
                    session["user_id"] = username
                    session["is_admin"] = is_admin
                    if db_user_id is not None:
                        session["db_user_id"] = db_user_id
                    session["login_at"] = datetime.now(UTC).isoformat()
                    session.permanent = remember_me
                    clear_failed_logins(user_db_path, username)
                    if user_db is not None and db_user_id is not None:
                        user_db.record_login(db_user_id)
                    logger.info(
                        "Login successful for user '%s' from IP %s (CWA auth, is_admin=%s, remember_me=%s)",
                        username,
                        ip_address,
                        is_admin,
                        remember_me,
                    )
                    return jsonify({"success": True})

                except _OPERATIONAL_ERRORS as e:
                    logger.error_trace(f"CWA database error during login: {e}")
                    return jsonify({"error": "Authentication system error"}), 500

            # Should not reach here, but handle gracefully
            return jsonify({"error": "Unknown authentication mode"}), 500

        except _OPERATIONAL_ERRORS as e:
            logger.error_trace(f"Login error: {e}")
            return jsonify({"error": "Login failed"}), 500

    @app.route("/api/auth/logout", methods=["POST"])
    def api_logout() -> Response | tuple[Response, int]:
        """Logout endpoint that clears the session.

        For proxy auth, returns the logout URL if configured.

        Returns:
            flask.Response: JSON with success status and optional logout_url.

        """
        try:
            auth_mode = get_auth_mode()
            ip_address = get_client_ip()
            username = session.get("user_id", "unknown")
            session.clear()
            logger.info("Logout successful for user '%s' from IP %s", username, ip_address)

            # For proxy auth, include logout URL if configured
            if auth_mode == "proxy":
                logout_url = app_config.get("PROXY_AUTH_LOGOUT_URL", "")
                if logout_url:
                    return jsonify({"success": True, "logout_url": logout_url})

            return jsonify({"success": True})
        except _OPERATIONAL_ERRORS as e:
            logger.error_trace(f"Logout error: {e}")
            return jsonify({"error": "Logout failed"}), 500

    @app.route("/api/auth/check", methods=["GET"])
    def api_auth_check() -> Response | tuple[Response, int]:
        """Check if user has a valid session.

        Returns:
            flask.Response: JSON with authentication status, whether auth is required,
            which auth mode is active, and whether user has admin privileges.

        """
        try:
            auth_mode = get_auth_mode()

            # If no authentication is configured, access is allowed (full admin)
            if auth_mode == "none":
                return jsonify(
                    {
                        "authenticated": True,
                        "auth_required": False,
                        "auth_mode": "none",
                        "is_admin": True,
                    }
                )

            # Check if user has a valid session
            is_authenticated = "user_id" in session

            is_admin = get_auth_check_admin_status(auth_mode, {}, session)

            display_name = None
            if is_authenticated and session.get("db_user_id") and user_db is not None:
                try:
                    db_user = user_db.get_user(user_id=session["db_user_id"])
                    if db_user:
                        display_name = db_user.get("display_name") or None
                except (sqlite3.Error, TypeError, ValueError) as exc:
                    logger.debug("Could not load display name for session user: %s", exc)

            response_data: dict[str, Any] = {
                "authenticated": is_authenticated,
                "auth_required": True,
                "auth_mode": auth_mode,
                "is_admin": is_admin if is_authenticated else False,
                "username": session.get("user_id") if is_authenticated else None,
                "display_name": display_name,
            }

            # Add logout URL for proxy auth if configured
            if auth_mode == "proxy" and app_config.get("PROXY_AUTH_USER_HEADER", ""):
                logout_url = app_config.get("PROXY_AUTH_LOGOUT_URL", "")
                if logout_url:
                    response_data["logout_url"] = logout_url

            # Add custom OIDC button label and SSO enforcement flags if configured
            if auth_mode == "oidc":
                oidc_button_label = app_config.get("OIDC_BUTTON_LABEL", "")
                if oidc_button_label:
                    response_data["oidc_button_label"] = oidc_button_label
                if HIDE_LOCAL_AUTH:
                    response_data["hide_local_auth"] = True
                if OIDC_AUTO_REDIRECT:
                    response_data["oidc_auto_redirect"] = True

            return jsonify(response_data)
        except _OPERATIONAL_ERRORS as e:
            logger.error_trace(f"Auth check error: {e}")
            return jsonify(
                {
                    "authenticated": False,
                    "auth_required": True,
                    "auth_mode": "unknown",
                    "is_admin": False,
                }
            )
