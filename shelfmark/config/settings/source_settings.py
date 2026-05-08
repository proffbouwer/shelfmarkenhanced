"""Download source, Cloudflare bypass, and mirror settings registration."""

from typing import Any

from shelfmark.core.settings_registry import (
    CheckboxField,
    HeadingField,
    NumberField,
    OrderableListField,
    PasswordField,
    SelectField,
    SettingsField,
    TagListField,
    TextField,
    register_group,
    register_on_save,
    register_settings,
)

register_group("direct_download", "Direct Download", icon="download", order=20)


def _log_external_bypasser_warning() -> None:
    """Log warning about external bypasser DNS limitations (called after config is available)."""
    from shelfmark.core.config import config
    from shelfmark.core.logger import setup_logger

    logger = setup_logger(__name__)

    if config.get("USING_EXTERNAL_BYPASSER", False) and config.get("USE_CF_BYPASS", True):
        logger.warning(
            "Using external bypasser (FlareSolverr). Note: FlareSolverr uses its own DNS resolution, "
            "not this application's custom DNS settings. If you experience DNS-related blocks, "
            "configure DNS at the Docker/system level for your FlareSolverr container, "
            "or consider using the internal bypasser which integrates with the app's DNS system."
        )


def _get_fast_source_options() -> list[dict[str, str | bool | int | None]]:
    """Fast download sources - configurable list shown in settings."""
    from shelfmark.core.config import config
    from shelfmark.core.mirrors import get_download_source_missing_mirror_reason

    has_donator_key = bool(config.get("AA_DONATOR_KEY", ""))
    aa_fast_reason = get_download_source_missing_mirror_reason("aa-fast")
    if not aa_fast_reason and not has_donator_key:
        aa_fast_reason = "Requires Donator Key"
    libgen_reason = get_download_source_missing_mirror_reason("libgen")

    return [
        {
            "id": "aa-fast",
            "label": "AA Fast Downloads",
            "description": "Fast downloads for donators",
            "isPinned": True,
            "isLocked": aa_fast_reason is not None,
            "disabledReason": aa_fast_reason,
        },
        {
            "id": "libgen",
            "label": "Library Genesis",
            "description": "Instant downloads, no bypass needed",
            "isPinned": True,
            "isLocked": libgen_reason is not None,
            "disabledReason": libgen_reason,
        },
    ]


def _get_fast_source_defaults() -> list[dict[str, str | bool]]:
    """Default values for fast sources display."""
    return [
        {"id": "aa-fast", "enabled": True},
        {"id": "libgen", "enabled": True},
    ]


def _get_slow_source_options() -> list[dict[str, str | bool | None]]:
    """Slow download sources - configurable order. All require bypasser."""
    from shelfmark.core.config import config
    from shelfmark.core.mirrors import get_download_source_missing_mirror_reason

    bypass_enabled = config.get("USE_CF_BYPASS", True)

    def _get_reason(source_id: str) -> str | None:
        mirror_reason = get_download_source_missing_mirror_reason(source_id)
        if mirror_reason:
            return mirror_reason
        if not bypass_enabled:
            return "Requires Cloudflare bypass"
        return None

    return [
        {
            "id": "aa-slow-nowait",
            "label": "AA Slow Downloads (No Waitlist)",
            "description": "Partner servers",
            "isLocked": _get_reason("aa-slow-nowait") is not None,
            "disabledReason": _get_reason("aa-slow-nowait"),
        },
        {
            "id": "aa-slow-wait",
            "label": "AA Slow Downloads (Waitlist)",
            "description": "Partner servers with countdown timer",
            "isLocked": _get_reason("aa-slow-wait") is not None,
            "disabledReason": _get_reason("aa-slow-wait"),
        },
        {
            "id": "welib",
            "label": "Welib",
            "description": "Alternative mirror",
            "isLocked": _get_reason("welib") is not None,
            "disabledReason": _get_reason("welib"),
        },
        {
            "id": "zlib",
            "label": "Zlib",
            "description": "Alternative mirror",
            "isLocked": _get_reason("zlib") is not None,
            "disabledReason": _get_reason("zlib"),
        },
    ]


def _get_slow_source_defaults() -> list[dict[str, str | bool]]:
    """Default source priority order for slow sources."""
    from shelfmark.config.env import _LEGACY_ALLOW_USE_WELIB

    return [
        {"id": "aa-slow-nowait", "enabled": True},
        {"id": "aa-slow-wait", "enabled": True},
        {"id": "welib", "enabled": _LEGACY_ALLOW_USE_WELIB},
        {"id": "zlib", "enabled": True},
    ]


def _string_setting(value: object) -> str:
    """Normalize free-form string settings used by select option builders."""
    return value if isinstance(value, str) else str(value or "")


def _get_aa_base_url_options() -> list[dict[str, str]]:
    """Build AA URL options dynamically from user-supplied mirrors."""
    from shelfmark.core.config import config
    from shelfmark.core.mirrors import get_aa_mirrors
    from shelfmark.core.utils import normalize_http_url

    options = [{"value": "auto", "label": "Auto (Recommended)"}]

    all_mirrors = get_aa_mirrors()

    configured_url = normalize_http_url(
        _string_setting(config.get("AA_BASE_URL", "auto")),
        default_scheme="https",
        allow_special=("auto",),
    )
    if configured_url and configured_url != "auto" and configured_url not in all_mirrors:
        all_mirrors = [configured_url, *all_mirrors]

    for url in all_mirrors:
        domain = url.replace("https://", "").replace("http://", "")
        label = domain
        if configured_url and url == configured_url:
            label = f"{domain} (configured)"
        options.append({"value": url, "label": label})

    return options


def _on_save_mirrors(values: dict[str, Any]) -> dict[str, Any]:
    """Normalize mirror list settings before persisting."""
    from shelfmark.core.utils import normalize_http_url

    mirror_list_keys = {
        "AA_MIRROR_URLS",
        "LIBGEN_MIRROR_URLS",
        "ZLIB_MIRROR_URLS",
        "WELIB_MIRROR_URLS",
    }

    for key in mirror_list_keys:
        raw_urls = values.get(key)
        if raw_urls is None:
            continue

        if isinstance(raw_urls, str):
            parts = [p.strip() for p in raw_urls.split(",") if p.strip()]
        elif isinstance(raw_urls, list):
            parts = [str(p).strip() for p in raw_urls if str(p).strip()]
        else:
            parts = []

        normalized: list[str] = []
        for url in parts:
            if url.lower() == "auto":
                continue
            norm = normalize_http_url(url, default_scheme="https")
            if norm and norm not in normalized:
                normalized.append(norm)

        values[key] = normalized

    return {"error": False, "values": values}


@register_settings(
    "download_sources", "Download Sources", icon="download", order=21, group="direct_download"
)
def download_source_settings() -> list[SettingsField]:
    """Return settings for download source behavior."""
    return [
        CheckboxField(
            key="DIRECT_DOWNLOAD_ENABLED",
            label="Enable Direct Download Source",
            description=(
                "Show Direct Download in release-source lists and allow Direct mode "
                "searches. Add your own mirror URLs in the Mirrors tab before using it."
            ),
            default=False,
        ),
        PasswordField(
            key="AA_DONATOR_KEY",
            label="Account Donator Key",
            description="Enables fast download access on AA. Get this from your donator account page.",
        ),
        HeadingField(
            key="source_priority_heading",
            title="Source Priority",
            description="Sources are tried in order until a download succeeds. Mirror-backed entries unlock automatically when you configure their mirrors.",
        ),
        OrderableListField(
            key="FAST_SOURCES_DISPLAY",
            label="Fast downloads",
            description="Always tried first, no waiting or bypass required.",
            options=_get_fast_source_options,
            default=_get_fast_source_defaults(),
        ),
        OrderableListField(
            key="SOURCE_PRIORITY",
            label="Slow downloads",
            description="Fallback sources, may have waiting. Requires bypasser. Drag to reorder.",
            options=_get_slow_source_options,
            default=_get_slow_source_defaults(),
        ),
        NumberField(
            key="MAX_RETRY",
            label="Max Retries",
            description="Maximum retry attempts for failed downloads.",
            default=10,
            min_value=1,
            max_value=50,
        ),
        NumberField(
            key="DEFAULT_SLEEP",
            label="Retry Delay (seconds)",
            description="Wait time between download retry attempts.",
            default=5,
            min_value=1,
            max_value=60,
        ),
        HeadingField(
            key="content_type_routing_heading",
            title="Content-Type Routing",
            description="Route downloads to different folders based on content type. Only applies to Direct download source.",
        ),
        CheckboxField(
            key="AA_CONTENT_TYPE_ROUTING",
            label="Enable Content-Type Routing",
            description="Override destination based on content type metadata.",
            default=False,
        ),
        TextField(
            key="AA_CONTENT_TYPE_DIR_FICTION",
            label="Fiction Books",
            placeholder="/books/fiction",
            show_when={"field": "AA_CONTENT_TYPE_ROUTING", "value": True},
        ),
        TextField(
            key="AA_CONTENT_TYPE_DIR_NON_FICTION",
            label="Non-Fiction Books",
            placeholder="/books/non-fiction",
            show_when={"field": "AA_CONTENT_TYPE_ROUTING", "value": True},
        ),
        TextField(
            key="AA_CONTENT_TYPE_DIR_UNKNOWN",
            label="Unknown Books",
            placeholder="/books/unknown",
            show_when={"field": "AA_CONTENT_TYPE_ROUTING", "value": True},
        ),
        TextField(
            key="AA_CONTENT_TYPE_DIR_MAGAZINE",
            label="Magazines",
            placeholder="/books/magazines",
            show_when={"field": "AA_CONTENT_TYPE_ROUTING", "value": True},
        ),
        TextField(
            key="AA_CONTENT_TYPE_DIR_COMIC",
            label="Comic Books",
            placeholder="/books/comics",
            show_when={"field": "AA_CONTENT_TYPE_ROUTING", "value": True},
        ),
        TextField(
            key="AA_CONTENT_TYPE_DIR_STANDARDS",
            label="Standards Documents",
            placeholder="/books/standards",
            show_when={"field": "AA_CONTENT_TYPE_ROUTING", "value": True},
        ),
        TextField(
            key="AA_CONTENT_TYPE_DIR_MUSICAL_SCORE",
            label="Musical Scores",
            placeholder="/books/scores",
            show_when={"field": "AA_CONTENT_TYPE_ROUTING", "value": True},
        ),
        TextField(
            key="AA_CONTENT_TYPE_DIR_OTHER",
            label="Other",
            placeholder="/books/other",
            show_when={"field": "AA_CONTENT_TYPE_ROUTING", "value": True},
        ),
    ]


@register_settings(
    "cloudflare_bypass", "Cloudflare Bypass", icon="shield", order=22, group="direct_download"
)
def cloudflare_bypass_settings() -> list[SettingsField]:
    """Return settings for Cloudflare bypass behavior."""
    return [
        CheckboxField(
            key="USE_CF_BYPASS",
            label="Enable Cloudflare Bypass",
            description="Attempt to bypass Cloudflare protection on download sites.",
            default=True,
            requires_restart=True,
        ),
        CheckboxField(
            key="USING_EXTERNAL_BYPASSER",
            label="Use External Bypasser",
            description="Use FlareSolverr or similar external service instead of built-in bypasser. Caution: May have limitations with custom DNS, Tor and proxies. You may experience slower downloads and and poorer reliability compared to the internal bypasser.",
            default=False,
            requires_restart=True,
        ),
        TextField(
            key="EXT_BYPASSER_URL",
            label="External Bypasser URL",
            description="URL of the external bypasser service (e.g., FlareSolverr).",
            default="http://flaresolverr:8191",
            placeholder="http://flaresolverr:8191",
            requires_restart=True,
            show_when={"field": "USING_EXTERNAL_BYPASSER", "value": True},
        ),
        TextField(
            key="EXT_BYPASSER_PATH",
            label="External Bypasser Path",
            description="API path for the external bypasser.",
            default="/v1",
            placeholder="/v1",
            requires_restart=True,
            show_when={"field": "USING_EXTERNAL_BYPASSER", "value": True},
        ),
        NumberField(
            key="EXT_BYPASSER_TIMEOUT",
            label="External Bypasser Timeout (ms)",
            description="Timeout for external bypasser requests in milliseconds.",
            default=60000,
            min_value=10000,
            max_value=300000,
            requires_restart=True,
            show_when={"field": "USING_EXTERNAL_BYPASSER", "value": True},
        ),
    ]


# Register the on_save handler for mirrors tab
register_on_save("mirrors", _on_save_mirrors)


@register_settings("mirrors", "Mirrors", icon="globe", order=23, group="direct_download")
def mirror_settings() -> list[SettingsField]:
    """Configure download source mirrors."""
    return [
        # === PRIMARY SOURCE ===
        HeadingField(
            key="aa_mirrors_heading",
            title="Anna's Archive",
            description=(
                "Add your own Anna's Archive mirror URLs here. Auto mode will try them in the "
                "order listed below."
            ),
        ),
        SelectField(
            key="AA_BASE_URL",
            label="Primary Mirror",
            description=(
                "Select Auto to try mirrors from your list on startup and fail over on errors. "
                "Choosing a specific mirror pins Shelfmark to that URL."
            ),
            options=_get_aa_base_url_options,
            default="auto",
        ),
        TagListField(
            key="AA_MIRROR_URLS",
            label="Mirrors",
            description=(
                "List the Anna's Archive mirror URLs you want Shelfmark to use. Type a URL and "
                "press Enter to add it. Order matters when Auto is selected."
            ),
            placeholder="https://your-aa-mirror.example",
            default=[],
        ),
        # === LIBGEN ===
        TagListField(
            key="LIBGEN_MIRROR_URLS",
            label="LibGen",
            description="Mirrors are tried in the order you add them until one works.",
            placeholder="https://your-libgen-mirror.example",
        ),
        # === Z-LIBRARY ===
        TagListField(
            key="ZLIB_MIRROR_URLS",
            label="Z-Library",
            description="Only the first mirror in the list is used.",
            placeholder="https://your-zlibrary-mirror.example",
        ),
        # === WELIB ===
        TagListField(
            key="WELIB_MIRROR_URLS",
            label="Welib",
            description="Only the first mirror in the list is used.",
            placeholder="https://your-welib-mirror.example",
        ),
    ]
