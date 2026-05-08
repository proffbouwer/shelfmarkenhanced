"""Network settings registration."""

from shelfmark.config import env
from shelfmark.core.settings_registry import (
    CheckboxField,
    SelectField,
    SettingsField,
    TextField,
    register_settings,
)


@register_settings("network", "Network", icon="globe", order=10)
def network_settings() -> list[SettingsField]:
    """Network and connectivity settings."""
    # Avoid querying the live config singleton while settings are still being
    # registered, which can recurse back into this module during import.
    tor_enabled = env.USING_TOR

    # When Tor is enabled, DNS/proxy settings are overridden by iptables rules
    # Tor uses iptables to force ALL traffic through Tor
    tor_overrides_network = tor_enabled  # Only override when Tor is actually active

    return [
        SelectField(
            key="CERTIFICATE_VALIDATION",
            label="Certificate Validation",
            description="Controls SSL/TLS certificate verification for outbound connections. Disable for self-signed certificates on internal services (e.g. OIDC providers, Prowlarr).",
            options=[
                {"value": "enabled", "label": "Enabled (Recommended)"},
                {"value": "disabled_local", "label": "Disabled for Local Addresses"},
                {"value": "disabled", "label": "Disabled"},
            ],
            default="enabled",
        ),
        SelectField(
            key="CUSTOM_DNS",
            label="DNS Provider",
            description=(
                "Managed by Tor when Tor routing is enabled."
                if tor_overrides_network
                else "DNS provider for domain resolution. 'Auto' rotates through providers on failure."
            ),
            options=[
                {"value": "auto", "label": "Auto (Recommended)"},
                {"value": "system", "label": "System"},
                {"value": "google", "label": "Google"},
                {"value": "cloudflare", "label": "Cloudflare"},
                {"value": "quad9", "label": "Quad9"},
                {"value": "opendns", "label": "OpenDNS"},
                {"value": "manual", "label": "Manual"},
            ],
            default="auto",
            disabled=tor_overrides_network,
            disabled_reason="DNS is managed by Tor when Tor routing is enabled.",
        ),
        TextField(
            key="CUSTOM_DNS_MANUAL",
            label="Manual DNS Servers",
            description="Comma-separated list of DNS server IP addresses (e.g., 8.8.8.8, 1.1.1.1).",
            placeholder="8.8.8.8, 1.1.1.1",
            disabled=tor_overrides_network,
            disabled_reason="DNS is managed by Tor when Tor routing is enabled.",
            show_when={"field": "CUSTOM_DNS", "value": "manual"},
        ),
        CheckboxField(
            key="USE_DOH",
            label="Use DNS over HTTPS",
            description=(
                "Not applicable when Tor routing is enabled."
                if tor_overrides_network
                else "Use encrypted DNS queries for improved reliability and privacy."
            ),
            default=True,
            disabled=tor_overrides_network,
            disabled_reason="DNS over HTTPS is not used when Tor routing is enabled.",
            # Hide for manual and system (no DoH endpoint available for custom IPs or system DNS)
            show_when={
                "field": "CUSTOM_DNS",
                "value": ["auto", "google", "cloudflare", "quad9", "opendns"],
            },
            # Disable for auto (always uses DoH)
            disabled_when={
                "field": "CUSTOM_DNS",
                "value": "auto",
                "reason": "Auto mode always uses DNS over HTTPS for reliable provider rotation.",
            },
        ),
        CheckboxField(
            key="USING_TOR",
            label="Tor Routing",
            description=(
                "All traffic is routed through Tor. Requires container restart to change."
                if tor_enabled
                else "Route all traffic through Tor for enhanced privacy. Requires root startup."
            ),
            default=tor_enabled,  # Reflects actual state from env var
            disabled=True,  # Tor state requires container restart
            disabled_reason=(
                "Tor routing is active. Set USING_TOR=false and restart to disable."
                if tor_enabled
                else "Set USING_TOR=true env var and restart as root."
            ),
        ),
        SelectField(
            key="PROXY_MODE",
            label="Proxy Mode",
            description=(
                "Not applicable when Tor routing is enabled."
                if tor_overrides_network
                else "Choose proxy type. SOCKS5 handles all traffic through a single proxy."
            ),
            options=[
                {"value": "none", "label": "None (Direct Connection)"},
                {"value": "http", "label": "HTTP/HTTPS Proxy"},
                {"value": "socks5", "label": "SOCKS5 Proxy"},
            ],
            default="none",
            disabled=tor_overrides_network,
            disabled_reason="Proxy settings are not used when Tor routing is enabled.",
        ),
        TextField(
            key="HTTP_PROXY",
            label="HTTP Proxy",
            description="HTTP proxy URL (e.g., http://proxy:8080)",
            placeholder="http://proxy:8080",
            disabled=tor_overrides_network,
            disabled_reason="Proxy settings are not used when Tor routing is enabled.",
            show_when={"field": "PROXY_MODE", "value": "http"},
        ),
        TextField(
            key="HTTPS_PROXY",
            label="HTTPS Proxy",
            description="HTTPS proxy URL (leave empty to use HTTP proxy for HTTPS)",
            placeholder="http://proxy:8080",
            disabled=tor_overrides_network,
            disabled_reason="Proxy settings are not used when Tor routing is enabled.",
            show_when={"field": "PROXY_MODE", "value": "http"},
        ),
        TextField(
            key="SOCKS5_PROXY",
            label="SOCKS5 Proxy",
            description="SOCKS5 proxy URL. Supports auth: socks5://user:pass@host:port",
            placeholder="socks5://localhost:1080",
            disabled=tor_overrides_network,
            disabled_reason="Proxy settings are not used when Tor routing is enabled.",
            show_when={"field": "PROXY_MODE", "value": "socks5"},
        ),
        TextField(
            key="NO_PROXY",
            label="No Proxy",
            description="Comma-separated hosts to bypass proxy (e.g., localhost,127.0.0.1,10.*,*.local)",
            disabled=tor_overrides_network,
            disabled_reason="Proxy settings are not used when Tor routing is enabled.",
            show_when={"field": "PROXY_MODE", "value": ["http", "socks5"]},
        ),
    ]
