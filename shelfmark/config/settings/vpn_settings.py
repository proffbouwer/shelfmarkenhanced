"""VPN (Gluetun) settings registration."""

from typing import Any

from shelfmark.core.settings_registry import (
    CheckboxField,
    CustomComponentField,
    HeadingField,
    PasswordField,
    SelectField,
    SettingsField,
    TextField,
    register_settings,
)


@register_settings("vpn", "VPN", icon="shield-check", order=8)
def vpn_settings() -> list[SettingsField]:
    """Gluetun VPN integration settings."""
    return [
        HeadingField(
            key="vpn_status_heading",
            title="VPN Status",
            description="Live status from the Gluetun control API.",
        ),
        CustomComponentField(
            key="vpn_status_widget",
            component="vpn_status",
            label="VPN Connection",
            wrap_in_field_wrapper=True,
        ),
        HeadingField(
            key="vpn_control_heading",
            title="Gluetun Control API",
            description=(
                "Shelfmark reads VPN status from the Gluetun HTTP control server. "
                "Configure the URL below to match your setup. "
                "When using the docker-compose.gluetun.yml overlay the default URL works automatically."
            ),
        ),
        TextField(
            key="GLUETUN_CONTROL_URL",
            label="Control API URL",
            description=(
                "Base URL of the Gluetun HTTP control server. "
                "Use http://gluetun:8000 when enhanced-shelfmark shares gluetun's network namespace, "
                "or http://localhost:8000 when port 8000 is mapped to the host."
            ),
            placeholder="http://gluetun:8000",
            default="http://gluetun:8000",
        ),
        PasswordField(
            key="GLUETUN_API_KEY",
            label="API Key (optional)",
            description=(
                "Bearer token for the Gluetun control API. Leave blank if you have configured "
                "HTTP_CONTROL_SERVER_AUTH_DEFAULT_ROLE to allow public read access."
            ),
            placeholder="",
            default="",
        ),
        HeadingField(
            key="vpn_provider_heading",
            title="VPN Provider",
            description=(
                "These settings correspond to Gluetun environment variables. "
                "They are displayed here for reference — apply changes by restarting the Gluetun container "
                "with the updated environment."
            ),
        ),
        SelectField(
            key="VPN_SERVICE_PROVIDER",
            label="Provider",
            description="Your VPN service provider.",
            options=[
                {"value": "mullvad", "label": "Mullvad"},
                {"value": "nordvpn", "label": "NordVPN"},
                {"value": "expressvpn", "label": "ExpressVPN"},
                {"value": "private internet access", "label": "Private Internet Access"},
                {"value": "protonvpn", "label": "ProtonVPN"},
                {"value": "surfshark", "label": "Surfshark"},
                {"value": "cyberghost", "label": "CyberGhost"},
                {"value": "ipvanish", "label": "IPVanish"},
                {"value": "custom", "label": "Custom"},
            ],
            default="mullvad",
        ),
        SelectField(
            key="VPN_TYPE",
            label="Protocol",
            description="VPN tunnel protocol.",
            options=[
                {"value": "wireguard", "label": "WireGuard (recommended)"},
                {"value": "openvpn", "label": "OpenVPN"},
            ],
            default="wireguard",
        ),
        TextField(
            key="SERVER_COUNTRIES",
            label="Server Countries",
            description="Comma-separated list of preferred server countries (e.g. Netherlands, Sweden).",
            placeholder="Netherlands",
            default="",
        ),
        TextField(
            key="SERVER_CITIES",
            label="Server Cities",
            description="Comma-separated list of preferred server cities (optional).",
            placeholder="Amsterdam",
            default="",
        ),
        CheckboxField(
            key="VPN_KILLSWITCH_INFO",
            label="Kill Switch Active",
            description=(
                "When using the Gluetun overlay, the kill switch is always active — "
                "all traffic is blocked if the VPN tunnel drops. "
                "This field is informational only."
            ),
            default=True,
            disabled=True,
            disabled_reason="Kill switch is managed by Gluetun, not by Shelfmark.",
        ),
    ]
