"""SAML2 SSO Flask route handlers.

Registers:
  GET  /api/auth/saml/login    — initiates the SP-initiated auth flow
  POST /api/auth/saml/callback — receives and validates the IdP Response
  GET  /api/auth/saml/metadata — serves the SP metadata XML
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode, urlsplit, urlunsplit

from flask import Flask, Response, jsonify, make_response, redirect, request, session

from shelfmark.core.config import config as app_config
from shelfmark.core.logger import setup_logger
from shelfmark.core.saml_auth import (
    build_auth_request,
    build_sp_metadata,
    process_response,
    provision_saml_user,
)

if TYPE_CHECKING:
    from shelfmark.core.user_db import UserDB

logger = setup_logger(__name__)

_RETURN_TO_SESSION_KEY = "saml_return_to"
AUTH_SOURCE_SAML = "saml"


def _get_sp_entity_id() -> str:
    entity_id = app_config.get("SAML_ENTITY_ID", "")
    if not entity_id:
        # Fall back to the request origin
        parts = urlsplit(request.url)
        entity_id = urlunsplit((parts.scheme, parts.netloc, "", "", ""))
    return entity_id


def _get_acs_url() -> str:
    """Absolute URL for the Assertion Consumer Service."""
    parts = urlsplit(request.url)
    base = urlunsplit((parts.scheme, parts.netloc, "", "", ""))
    return f"{base}/api/auth/saml/callback"


def _prepare_request_data() -> dict[str, Any]:
    """Build the request dict expected by python3-saml."""
    parts = urlsplit(request.url)
    return {
        "https": "on" if parts.scheme == "https" else "off",
        "http_host": request.host,
        "script_name": request.path,
        "get_data": request.args.copy(),
        "post_data": request.form.copy(),
    }


def _login_error_url(message: str) -> str:
    parts = urlsplit(request.url)
    base = urlunsplit((parts.scheme, parts.netloc, "", "", ""))
    qs = urlencode({"error": message})
    return f"{base}/login?{qs}"


def _post_login_redirect(return_to: str | None = None) -> str:
    parts = urlsplit(request.url)
    base = urlunsplit((parts.scheme, parts.netloc, "", "", ""))
    if return_to and return_to.startswith("/") and not return_to.startswith("//"):
        return f"{base}{return_to}"
    return base


def register_saml_routes(app: Flask, user_db: UserDB) -> None:
    """Register SAML2 routes on the Flask app."""

    @app.route("/api/auth/saml/login", methods=["GET"])
    def saml_login() -> Response:
        """Redirect to the IdP for authentication."""
        auth_mode = app_config.get("AUTH_METHOD", "none")
        if auth_mode != "saml":
            return jsonify({"error": "SAML authentication is not enabled"}), 400

        return_to = request.args.get("return_to", "")
        if return_to:
            session[_RETURN_TO_SESSION_KEY] = return_to

        try:
            redirect_url = build_auth_request(
                sp_entity_id=_get_sp_entity_id(),
                acs_url=_get_acs_url(),
                request_data=_prepare_request_data(),
            )
            return redirect(redirect_url)
        except Exception:
            logger.exception("SAML login init error")
            return redirect(_login_error_url("Failed to initiate SAML login"))

    @app.route("/api/auth/saml/callback", methods=["POST"])
    def saml_callback() -> Response:
        """Receive and validate the IdP SAML Response."""
        auth_mode = app_config.get("AUTH_METHOD", "none")
        if auth_mode != "saml":
            return jsonify({"error": "SAML authentication is not enabled"}), 400

        try:
            user_info = process_response(
                sp_entity_id=_get_sp_entity_id(),
                acs_url=_get_acs_url(),
                request_data=_prepare_request_data(),
            )
        except ValueError as exc:
            logger.warning("SAML callback validation error: %s", exc)
            return redirect(_login_error_url(str(exc)))
        except Exception:
            logger.exception("SAML callback unexpected error")
            return redirect(_login_error_url("Authentication failed"))

        auto_provision = bool(app_config.get("SAML_AUTO_PROVISION", True))

        user = provision_saml_user(
            user_db=user_db,
            subject=user_info["subject"],
            username=user_info["username"],
            email=user_info.get("email"),
            display_name=user_info.get("display_name"),
            auto_provision=auto_provision,
        )

        if user is None:
            logger.warning(
                "SAML login rejected: auto-provision disabled for %s",
                user_info["username"],
            )
            return redirect(_login_error_url("Account not found. Contact your administrator."))

        session["user_id"] = user["username"]
        session["is_admin"] = user.get("role") == "admin"
        session["db_user_id"] = user["id"]
        session["login_at"] = datetime.now(UTC).isoformat()
        session.permanent = True

        return_to = session.pop(_RETURN_TO_SESSION_KEY, None)
        logger.info(
            "SAML login successful: %s (admin=%s)",
            user["username"],
            user.get("role") == "admin",
        )
        return redirect(_post_login_redirect(return_to))

    @app.route("/api/auth/saml/metadata", methods=["GET"])
    def saml_metadata() -> Response:
        """Return the SP metadata XML."""
        try:
            metadata_xml = build_sp_metadata(
                sp_entity_id=_get_sp_entity_id(),
                acs_url=_get_acs_url(),
            )
        except Exception:
            logger.exception("Failed to generate SP metadata")
            return jsonify({"error": "Failed to generate SP metadata"}), 500

        resp = make_response(metadata_xml)
        resp.headers["Content-Type"] = "application/xml"
        return resp
