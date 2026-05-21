"""SAML2 authentication helpers.

Wraps python3-saml to handle SP metadata, IdP metadata fetching,
assertion validation, and user provisioning.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from shelfmark.core.config import config as app_config
from shelfmark.core.logger import setup_logger

if TYPE_CHECKING:
    from shelfmark.core.user_db import UserDB

logger = setup_logger(__name__)


def _get_saml_settings(sp_entity_id: str, acs_url: str) -> dict[str, Any]:
    """Build the python3-saml settings dict from app config."""
    idp_metadata_url = app_config.get("SAML_IDP_METADATA_URL", "")
    idp_sso_url = app_config.get("SAML_IDP_SSO_URL", "")
    idp_x509_cert = app_config.get("SAML_IDP_X509_CERT", "")

    idp: dict[str, Any] = {}
    if idp_sso_url:
        idp = {
            "entityId": idp_sso_url,
            "singleSignOnService": {
                "url": idp_sso_url,
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
            },
            "x509cert": idp_x509_cert,
        }

    return {
        "strict": True,
        "debug": False,
        "sp": {
            "entityId": sp_entity_id,
            "assertionConsumerService": {
                "url": acs_url,
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
            },
            "NameIDFormat": "urn:oasis:names:tc:SAML:1.1:nameid-format:unspecified",
        },
        "idp": idp,
    }


def _load_idp_from_metadata(settings: dict[str, Any]) -> dict[str, Any]:
    """Fetch IdP metadata XML and overwrite the idp section of settings."""
    import requests  # noqa: PLC0415
    from onelogin.saml2.idp_metadata_parser import OneLogin_Saml2_IdPMetadataParser  # noqa: PLC0415

    idp_metadata_url = app_config.get("SAML_IDP_METADATA_URL", "")
    if not idp_metadata_url:
        return settings

    try:
        resp = requests.get(idp_metadata_url, timeout=10)
        resp.raise_for_status()
        remote_settings = OneLogin_Saml2_IdPMetadataParser.parse(resp.text)
        settings["idp"] = remote_settings.get("idp", settings["idp"])
        logger.debug("Loaded IdP metadata from %s", idp_metadata_url)
    except Exception:
        logger.exception("Failed to load IdP metadata from %s", idp_metadata_url)

    return settings


def build_auth_request(sp_entity_id: str, acs_url: str, request_data: dict[str, Any]) -> str:
    """Return the redirect URL for the SAML AuthnRequest."""
    from onelogin.saml2.auth import OneLogin_Saml2_Auth  # noqa: PLC0415

    settings = _get_saml_settings(sp_entity_id, acs_url)
    settings = _load_idp_from_metadata(settings)

    auth = OneLogin_Saml2_Auth(request_data, settings)
    return auth.login()


def process_response(
    sp_entity_id: str,
    acs_url: str,
    request_data: dict[str, Any],
) -> dict[str, Any]:
    """Validate the SAML Response POST and return normalised user attributes.

    Returns a dict with keys: ``subject``, ``username``, ``email``, ``display_name``.
    Raises ``ValueError`` with a human-readable message on failure.
    """
    from onelogin.saml2.auth import OneLogin_Saml2_Auth  # noqa: PLC0415

    settings = _get_saml_settings(sp_entity_id, acs_url)
    settings = _load_idp_from_metadata(settings)

    auth = OneLogin_Saml2_Auth(request_data, settings)
    auth.process_response()

    errors = auth.get_errors()
    if errors:
        reason = auth.get_last_error_reason() or ", ".join(errors)
        raise ValueError(f"SAML response validation failed: {reason}")

    if not auth.is_authenticated():
        raise ValueError("SAML authentication was not successful")

    attrs = auth.get_attributes()
    name_id = auth.get_nameid() or ""

    email_attr = app_config.get("SAML_ATTR_EMAIL", "email") or "email"
    username_attr = app_config.get("SAML_ATTR_USERNAME", "") or ""

    def _first(key: str) -> str:
        val = attrs.get(key, [])
        return str(val[0]) if val else ""

    email = _first(email_attr)
    username = _first(username_attr) if username_attr else ""
    if not username:
        username = email.split("@")[0] if email else name_id

    # Display name heuristic: try common attributes
    display_name = _first("displayName") or _first("cn") or username

    return {
        "subject": name_id,
        "username": username,
        "email": email or None,
        "display_name": display_name or None,
    }


def build_sp_metadata(sp_entity_id: str, acs_url: str) -> str:
    """Return the SP metadata XML string."""
    from onelogin.saml2.settings import OneLogin_Saml2_Settings  # noqa: PLC0415

    settings_dict = _get_saml_settings(sp_entity_id, acs_url)
    saml_settings = OneLogin_Saml2_Settings(settings=settings_dict, sp_validation_only=True)
    metadata = saml_settings.get_sp_metadata()
    errors = saml_settings.validate_metadata(metadata)
    if errors:
        logger.warning("SP metadata validation errors: %s", errors)
    return metadata if isinstance(metadata, str) else metadata.decode()


def provision_saml_user(
    user_db: UserDB,
    subject: str,
    username: str,
    email: str | None,
    display_name: str | None,
    *,
    auto_provision: bool = True,
) -> dict[str, Any] | None:
    """Upsert the SAML user in users.db.

    Returns the user dict or None if auto-provision is disabled and the user
    doesn't already exist.
    """
    existing = user_db.get_user_by_saml_subject(subject)
    if existing:
        user_db.record_login(existing["id"])
        return existing

    if not auto_provision:
        return None

    return user_db.upsert_saml_user(
        saml_subject=subject,
        username=username,
        email=email,
        display_name=display_name,
    )
