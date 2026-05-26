"""VPN status routes.

Provides GET /api/vpn/status which proxies the Gluetun HTTP control API
and returns a normalised status suitable for the frontend indicator.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import requests

from flask import Flask, Response, jsonify

from shelfmark.core.auth_middleware import login_required
from shelfmark.core.config import config as app_config
from shelfmark.core.logger import setup_logger

if TYPE_CHECKING:
    pass

logger = setup_logger(__name__)

_TIMEOUT = 4  # seconds


def _gluetun_url() -> str:
    base = str(app_config.get("GLUETUN_CONTROL_URL", "") or "").rstrip("/")
    return base or "http://gluetun:8000"


def _auth_headers() -> dict[str, str]:
    api_key = str(app_config.get("GLUETUN_API_KEY", "") or "").strip()
    if api_key:
        return {"Authorization": f"Bearer {api_key}"}
    return {}


def _fetch_json(path: str) -> tuple[dict[str, Any] | None, str | None]:
    """GET a Gluetun API path and return (data, error_message)."""
    url = f"{_gluetun_url()}{path}"
    try:
        resp = requests.get(url, headers=_auth_headers(), timeout=_TIMEOUT)
        if resp.status_code == 401:
            return None, "unauthorized"
        if resp.status_code == 404:
            return None, "not_found"
        resp.raise_for_status()
        return resp.json(), None
    except requests.exceptions.ConnectionError:
        return None, "unreachable"
    except requests.exceptions.Timeout:
        return None, "timeout"
    except Exception as exc:  # noqa: BLE001
        logger.debug("Gluetun API error at %s: %s", path, exc)
        return None, "error"


def register_vpn_routes(app: Flask) -> None:
    """Register VPN status routes on the Flask app."""

    @app.route("/api/vpn/status", methods=["GET"])
    @login_required
    def vpn_status() -> Response | tuple[Response, int]:
        """Return VPN connection status from Gluetun control API."""
        vpn_data, vpn_err = _fetch_json("/v1/vpn/status")
        ip_data, ip_err = _fetch_json("/v1/publicip/ip")

        if vpn_err == "unreachable":
            return jsonify({
                "status": "not_configured",
                "message": "Gluetun control API is unreachable. Check GLUETUN_CONTROL_URL.",
                "connected": False,
                "public_ip": None,
                "country": None,
            })

        if vpn_err == "unauthorized":
            return jsonify({
                "status": "unauthorized",
                "message": "Gluetun API requires authentication. Set GLUETUN_API_KEY in VPN settings.",
                "connected": False,
                "public_ip": None,
                "country": None,
            })

        if vpn_err:
            return jsonify({
                "status": "unknown",
                "message": f"Could not reach Gluetun control API ({vpn_err}).",
                "connected": False,
                "public_ip": None,
                "country": None,
            })

        raw_status = str((vpn_data or {}).get("status", "")).lower()
        connected = raw_status == "running"

        return jsonify({
            "status": raw_status or "unknown",
            "message": "Connected" if connected else "Disconnected",
            "connected": connected,
            "public_ip": (ip_data or {}).get("public_ip") if not ip_err else None,
            "country": (ip_data or {}).get("country") if not ip_err else None,
            "city": (ip_data or {}).get("city") if not ip_err else None,
        })
