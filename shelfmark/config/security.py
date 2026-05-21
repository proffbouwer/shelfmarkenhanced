"""Authentication settings registration."""

from typing import TYPE_CHECKING, Any

from shelfmark.config.migrations import migrate_security_settings
from shelfmark.config.security_handlers import (
    check_oidc_connection,
    on_save_security,
)
from shelfmark.core.config import config as app_config
from shelfmark.core.logger import setup_logger
from shelfmark.core.settings_registry import (
    ActionButton,
    CheckboxField,
    CustomComponentField,
    PasswordField,
    SelectField,
    SettingsField,
    TagListField,
    TextField,
    load_config_file,
    register_on_save,
    register_settings,
)
from shelfmark.core.user_db import sync_builtin_admin_user

if TYPE_CHECKING:
    from collections.abc import Callable

logger = setup_logger(__name__)


def _auth_condition(auth_method: str) -> dict[str, str]:
    return {"field": "AUTH_METHOD", "value": auth_method}


def _auth_field(factory: Callable[..., Any], auth_method: str, **kwargs: Any) -> Any:
    return factory(show_when=_auth_condition(auth_method), **kwargs)


def _migrate_security_settings() -> None:
    from shelfmark.core.settings_registry import (
        _ensure_config_dir,
        _get_config_file_path,
        save_config_file,
    )

    def _save_users_config(values: dict[str, Any]) -> None:
        save_config_file("users", values)

    migrate_security_settings(
        load_security_config=lambda: load_config_file("security"),
        load_users_config=lambda: load_config_file("users"),
        save_users_config=_save_users_config,
        ensure_config_dir=lambda: _ensure_config_dir("security"),
        get_config_path=lambda: _get_config_file_path("security"),
        sync_builtin_admin_user=sync_builtin_admin_user,
        logger=logger,
    )


def _on_save_security(values: dict[str, Any]) -> dict[str, Any]:
    return on_save_security(values)


def _test_oidc_connection(current_values: dict[str, Any] | None = None) -> dict[str, Any]:
    return check_oidc_connection(
        load_security_config=lambda: {
            "OIDC_DISCOVERY_URL": app_config.get("OIDC_DISCOVERY_URL", ""),
        },
        current_values=current_values or {},
        logger=logger,
    )


@register_settings("security", "Security", icon="shield", order=5)
def security_settings() -> list[SettingsField]:
    """Security and authentication settings."""
    from shelfmark.config.env import CWA_DB_PATH

    cwa_db_available = CWA_DB_PATH is not None and CWA_DB_PATH.exists()

    auth_method_options = [
        {"label": "No Authentication", "value": "none"},
        {"label": "Local", "value": "builtin"},
        {"label": "Proxy Authentication", "value": "proxy"},
        {"label": "OIDC (OpenID Connect)", "value": "oidc"},
        {"label": "SAML2 SSO", "value": "saml"},
        {"label": "Calibre-Web Database", "value": "cwa"},
    ]

    fields = [
        SelectField(
            key="AUTH_METHOD",
            label="Authentication Method",
            description=(
                "Select the authentication method for accessing Shelfmark. "
                "Restart container after changing Calibre-Web passwords."
            ),
            options=auth_method_options,
            default="none",
        ),
        CustomComponentField(
            key="builtin_admin_requirement",
            component="oidc_admin_hint",
            label=(
                "Local authentication is inactive until a local admin account with a "
                "password is created."
            ),
            show_when=_auth_condition("builtin"),
        ),
        CustomComponentField(
            key="oidc_admin_requirement",
            component="oidc_admin_hint",
            label="A local admin account is required before OIDC can be enabled.",
            show_when=_auth_condition("oidc"),
        ),
        *(
            []
            if cwa_db_available
            else [
                CustomComponentField(
                    key="cwa_db_missing",
                    component="oidc_admin_hint",
                    label=(
                        "Calibre-Web database not detected. Mount your app.db to "
                        "/auth/app.db to enable this method. Authentication will fall "
                        "back to none until the database is available."
                    ),
                    show_when=_auth_condition("cwa"),
                ),
            ]
        ),
        ActionButton(
            key="open_users_tab",
            label="Go to Users",
            description="Configure local users and admin access in the Users tab.",
            style="primary",
            show_when={"field": "AUTH_METHOD", "value": ["builtin", "oidc"]},
        ),
        _auth_field(
            TextField,
            "proxy",
            key="PROXY_AUTH_USER_HEADER",
            label="Proxy Auth User Header",
            description="The HTTP header your proxy uses to pass the authenticated username.",
            placeholder="e.g. X-Auth-User",
            default="X-Auth-User",
        ),
        _auth_field(
            TextField,
            "proxy",
            key="PROXY_AUTH_LOGOUT_URL",
            label="Proxy Auth Logout URL",
            description="The URL to redirect users to for logging out. Leave empty to disable logout functionality.",
            placeholder="https://myauth.example.com/logout",
            default="",
        ),
        _auth_field(
            TextField,
            "proxy",
            key="PROXY_AUTH_ADMIN_GROUP_HEADER",
            label="Proxy Auth Admin Group Header",
            description="Optional: header your proxy uses to pass user groups/roles.",
            placeholder="e.g. X-Auth-Groups",
            default="X-Auth-Groups",
        ),
        _auth_field(
            TextField,
            "proxy",
            key="PROXY_AUTH_ADMIN_GROUP_NAME",
            label="Proxy Auth Admin Group",
            description="Optional: users in this group are treated as admins. Leave blank to skip group-based admin detection.",
            placeholder="e.g. admins",
            default="",
        ),
    ]

    fields.append(
        CustomComponentField(
            key="oidc_callback_url",
            component="settings_label",
            label="Callback URL",
            description="{origin}/api/auth/oidc/callback",
            show_when=_auth_condition("oidc"),
        )
    )

    oidc_specs = [
        (
            TextField,
            {
                "key": "OIDC_DISCOVERY_URL",
                "label": "Discovery URL",
                "description": "OpenID Connect discovery endpoint URL. Usually ends with /.well-known/openid-configuration.",
                "placeholder": "https://auth.example.com/.well-known/openid-configuration",
                "required": True,
            },
        ),
        (
            TextField,
            {
                "key": "OIDC_CLIENT_ID",
                "label": "Client ID",
                "description": "OAuth2 client ID from your identity provider.",
                "placeholder": "shelfmark",
                "required": True,
            },
        ),
        (
            PasswordField,
            {
                "key": "OIDC_CLIENT_SECRET",
                "label": "Client Secret",
                "description": "OAuth2 client secret from your identity provider.",
                "required": True,
            },
        ),
        (
            TagListField,
            {
                "key": "OIDC_SCOPES",
                "label": "Scopes",
                "description": "OAuth2 scopes to request from the identity provider. Managed automatically: includes essential scopes and the group claim when using admin group authorization.",
                "default": ["openid", "email", "profile"],
            },
        ),
        (
            TextField,
            {
                "key": "OIDC_GROUP_CLAIM",
                "label": "Group Claim Name",
                "description": "The name of the claim in the ID token that contains user groups.",
                "placeholder": "groups",
                "default": "groups",
            },
        ),
        (
            TextField,
            {
                "key": "OIDC_ADMIN_GROUP",
                "label": "Admin Group Name",
                "description": "Users in this group will be given admin access (if enabled below). Leave empty to use database roles only.",
                "placeholder": "shelfmark-admins",
                "default": "",
            },
        ),
        (
            CheckboxField,
            {
                "key": "OIDC_USE_ADMIN_GROUP",
                "label": "Use Admin Group for Authorization",
                "description": "When enabled, users in the Admin Group are granted admin access. When disabled, admin access is determined solely by database roles.",
                "default": True,
            },
        ),
        (
            CheckboxField,
            {
                "key": "OIDC_AUTO_PROVISION",
                "label": "Auto-Provision Users",
                "description": "Automatically create a user account on first OIDC login. When disabled, users must be pre-created by an admin.",
                "default": True,
            },
        ),
        (
            TextField,
            {
                "key": "OIDC_BUTTON_LABEL",
                "label": "Login Button Label",
                "description": "Custom label for the OIDC sign-in button on the login page.",
                "placeholder": "Sign in with OIDC",
                "default": "",
            },
        ),
        (
            TextField,
            {
                "key": "OIDC_EMAIL_CLAIM",
                "label": "Email Claim",
                "description": "ID token claim that contains the user's email address. Leave blank to use the standard 'email' claim.",
                "placeholder": "email",
                "default": "",
            },
        ),
        (
            TextField,
            {
                "key": "OIDC_USERNAME_CLAIM",
                "label": "Username Claim",
                "description": "ID token claim to use as the username. Leave blank to use the standard 'preferred_username' or 'sub' claim.",
                "placeholder": "preferred_username",
                "default": "",
            },
        ),
        (
            CheckboxField,
            {
                "key": "HIDE_LOCAL_AUTH",
                "label": "Hide Local Login Form",
                "description": "When OIDC is active, hide the username/password login form so users can only sign in via OIDC.",
                "default": False,
            },
        ),
        (
            CheckboxField,
            {
                "key": "OIDC_AUTO_REDIRECT",
                "label": "Auto-Redirect to OIDC",
                "description": "Automatically redirect unauthenticated users to the OIDC provider instead of showing the login page.",
                "default": False,
            },
        ),
    ]
    fields.extend(_auth_field(factory, "oidc", **spec) for factory, spec in oidc_specs)
    fields.append(
        ActionButton(
            key="test_oidc",
            label="Test Connection",
            description="Fetch the OIDC discovery document and validate configuration.",
            style="primary",
            callback=_test_oidc_connection,
            show_when=_auth_condition("oidc"),
        )
    )
    fields.append(
        CustomComponentField(
            key="oidc_env_info",
            component="oidc_env_info",
            label="Environment-Only Options",
            description="These options can only be set via environment variables because changing them through the UI could lock you out of the application.",
            wrap_in_field_wrapper=True,
            show_when=_auth_condition("oidc"),
        )
    )

    # ── SAML2 settings ─────────────────────────────────────────────────────
    saml_specs: list[tuple[type, dict[str, Any]]] = [
        (
            TextField,
            {
                "key": "SAML_ENTITY_ID",
                "label": "SP Entity ID",
                "description": "Service Provider entity ID (usually your application URL).",
                "placeholder": "https://shelfmark.example.com",
                "required": True,
            },
        ),
        (
            TextField,
            {
                "key": "SAML_IDP_METADATA_URL",
                "label": "IdP Metadata URL",
                "description": "URL to fetch IdP metadata XML. Takes precedence over manual SSO URL / certificate fields.",
                "placeholder": "https://idp.example.com/metadata.xml",
            },
        ),
        (
            TextField,
            {
                "key": "SAML_IDP_SSO_URL",
                "label": "IdP SSO URL",
                "description": "IdP Single Sign-On URL (used when no metadata URL is provided).",
                "placeholder": "https://idp.example.com/sso",
            },
        ),
        (
            TextField,
            {
                "key": "SAML_IDP_X509_CERT",
                "label": "IdP X.509 Certificate",
                "description": "IdP signing certificate (PEM, without header/footer). Required when not using a metadata URL.",
                "placeholder": "MIIC...",
            },
        ),
        (
            TextField,
            {
                "key": "SAML_ATTR_EMAIL",
                "label": "Email Attribute",
                "description": "SAML attribute name containing the user's email.",
                "placeholder": "email",
                "default": "email",
            },
        ),
        (
            TextField,
            {
                "key": "SAML_ATTR_USERNAME",
                "label": "Username Attribute",
                "description": "SAML attribute name to use as the username. Falls back to NameID if blank.",
                "placeholder": "uid",
                "default": "",
            },
        ),
        (
            CheckboxField,
            {
                "key": "SAML_AUTO_PROVISION",
                "label": "Auto-Provision Users",
                "description": "Automatically create a user account on first SAML login.",
                "default": True,
            },
        ),
        (
            TextField,
            {
                "key": "SAML_BUTTON_LABEL",
                "label": "Login Button Label",
                "description": "Custom label for the SAML sign-in button on the login page.",
                "placeholder": "Sign in with SSO",
                "default": "",
            },
        ),
    ]
    fields.extend(_auth_field(factory, "saml", **spec) for factory, spec in saml_specs)

    return fields


register_on_save("security", _on_save_security)
