"""Advanced settings registration."""

from typing import Any

from shelfmark.core.settings_registry import (
    ActionButton,
    CheckboxField,
    HeadingField,
    NumberField,
    SelectField,
    SettingsField,
    TableField,
    TextField,
    register_on_save,
    register_settings,
)

# These helpers are defined in general_settings and imported here to be used as callbacks.
# They are imported lazily via the callback mechanism, so we reference them by importing
# from the sibling module.
from shelfmark.config.settings.general_settings import _clear_covers_cache, _clear_metadata_cache


def _on_save_advanced(values: dict[str, Any]) -> dict[str, Any]:
    """Validate advanced settings before persisting."""
    from shelfmark.core.logger import setup_logger

    logger = setup_logger(__name__)

    mappings = values.get("PROWLARR_REMOTE_PATH_MAPPINGS")
    if mappings is None:
        return {"error": False, "values": values}

    if not isinstance(mappings, list):
        return {
            "error": True,
            "message": "Remote path mappings must be a list",
            "values": values,
        }

    logger.debug("Processing %d remote path mapping entries", len(mappings))

    cleaned = []
    for i, entry in enumerate(mappings):
        if not isinstance(entry, dict):
            logger.debug("Skipping entry %d: not a dict", i)
            continue

        host = str(entry.get("host", "") or "").strip().lower()
        remote_path = str(entry.get("remotePath", "") or "").strip()
        local_path = str(entry.get("localPath", "") or "").strip()

        if not host or not remote_path or not local_path:
            logger.debug(
                "Skipping entry %d: missing field(s) - host=%s, remotePath=%s, localPath=%s",
                i,
                host,
                remote_path,
                local_path,
            )
            continue

        if not local_path.startswith("/"):
            return {
                "error": True,
                "message": f"Local Path must be an absolute path (got: {local_path})",
                "values": values,
            }

        cleaned.append({"host": host, "remotePath": remote_path, "localPath": local_path})

    logger.info("Saved %d remote path mapping(s)", len(cleaned))
    if cleaned:
        for m in cleaned:
            logger.debug(
                "  Mapping: %s -> %s (client: %s)", m["remotePath"], m["localPath"], m["host"]
            )

    values["PROWLARR_REMOTE_PATH_MAPPINGS"] = cleaned
    return {"error": False, "values": values}


@register_settings("advanced", "Advanced", icon="cog", order=15)
def advanced_settings() -> list[SettingsField]:
    """Advanced settings for power users."""
    return [
        TextField(
            key="URL_BASE",
            label="Base Path",
            description="Optional URL path prefix. Use a path like /shelfmark (no hostname). Leave blank for root.",
            placeholder="/shelfmark",
            requires_restart=True,
        ),
        CheckboxField(
            key="DEBUG",
            label="Debug Mode",
            description="Enable verbose logging to console and file. Not recommended for normal use.",
            default=False,
            requires_restart=True,
        ),
        NumberField(
            key="MAIN_LOOP_SLEEP_TIME",
            label="Queue Check Interval (seconds)",
            description="How often the download queue is checked for new items.",
            default=5,
            min_value=1,
            max_value=60,
            requires_restart=True,
        ),
        NumberField(
            key="DOWNLOAD_PROGRESS_UPDATE_INTERVAL",
            label="Progress Update Interval (seconds)",
            description="How often download progress is broadcast to the UI.",
            default=1,
            min_value=1,
            max_value=10,
            requires_restart=True,
        ),
        TextField(
            key="CUSTOM_SCRIPT",
            label="Custom Script Path",
            description="Path to a script to run after each successful download. Must be executable.",
            placeholder="/path/to/script.sh",
        ),
        SelectField(
            key="CUSTOM_SCRIPT_PATH_MODE",
            label="Custom Script Path Mode",
            description="Pass the path to the custom script as an absolute path or relative to the destination folder.",
            options=[
                {
                    "value": "absolute",
                    "label": "Absolute",
                    "description": "Pass the full destination path (default).",
                },
                {
                    "value": "relative",
                    "label": "Relative",
                    "description": "Pass the path relative to the destination folder.",
                },
            ],
            default="absolute",
        ),
        CheckboxField(
            key="CUSTOM_SCRIPT_JSON_PAYLOAD",
            label="Custom Script JSON Payload",
            description="Send a JSON payload to the script via stdin. Useful for multi-file imports (audiobooks) or richer metadata without relying on path parsing.",
            default=False,
        ),
        HeadingField(
            key="remote_path_mappings_heading",
            title="Remote Path Mappings",
            description="Map download client paths to paths inside Shelfmark. Needed when volume mounts differ between containers.",
        ),
        TableField(
            key="PROWLARR_REMOTE_PATH_MAPPINGS",
            label="Path Mappings",
            columns=[
                {
                    "key": "host",
                    "label": "Client",
                    "type": "select",
                    "options": [
                        {"value": "qbittorrent", "label": "qBittorrent"},
                        {"value": "transmission", "label": "Transmission"},
                        {"value": "deluge", "label": "Deluge"},
                        {"value": "rtorrent", "label": "rTorrent"},
                        {"value": "nzbget", "label": "NZBGet"},
                        {"value": "sabnzbd", "label": "SABnzbd"},
                    ],
                    "defaultValue": "qbittorrent",
                },
                {
                    "key": "remotePath",
                    "label": "Remote Path",
                    "type": "path",
                },
                {
                    "key": "localPath",
                    "label": "Local Path",
                    "type": "path",
                },
            ],
            default=[],
            add_label="Add Mapping",
            empty_message="No mappings configured.",
            env_supported=False,
        ),
        HeadingField(
            key="covers_cache_heading",
            title="Cover Image Cache",
            description="Cache book cover images locally for faster loading. Works for both Direct Download and Universal mode.",
        ),
        CheckboxField(
            key="COVERS_CACHE_ENABLED",
            label="Enable Cover Cache",
            description="Cache book covers on the server for faster loading.",
            default=True,
        ),
        NumberField(
            key="COVERS_CACHE_TTL",
            label="Cache TTL (days)",
            description="How long to keep cached covers. Set to 0 to keep forever (recommended for static artwork).",
            default=0,
            min_value=0,
            max_value=365,
        ),
        NumberField(
            key="COVERS_CACHE_MAX_SIZE_MB",
            label="Max Cache Size (MB)",
            description="Maximum disk space for cached covers. Oldest images are removed when limit is reached.",
            default=500,
            min_value=50,
            max_value=5000,
        ),
        ActionButton(
            key="clear_covers_cache",
            label="Clear Cover Cache",
            description="Delete all cached cover images.",
            style="danger",
            callback=_clear_covers_cache,
        ),
        HeadingField(
            key="metadata_cache_heading",
            title="Metadata Cache",
            description="Cache book metadata from providers (Hardcover, Open Library) to reduce API calls and speed up repeated searches.",
        ),
        CheckboxField(
            key="METADATA_CACHE_ENABLED",
            label="Enable Metadata Caching",
            description="When disabled, all metadata searches hit the provider API directly.",
            default=True,
        ),
        NumberField(
            key="METADATA_CACHE_SEARCH_TTL",
            label="Search Results Cache (seconds)",
            description="How long to cache search results. Default: 300 (5 minutes). Max: 604800 (7 days).",
            default=300,
            min_value=60,
            max_value=604800,
            show_when={"field": "METADATA_CACHE_ENABLED", "value": True},
        ),
        NumberField(
            key="METADATA_CACHE_BOOK_TTL",
            label="Book Details Cache (seconds)",
            description="How long to cache individual book details. Default: 600 (10 minutes). Max: 604800 (7 days).",
            default=600,
            min_value=60,
            max_value=604800,
            show_when={"field": "METADATA_CACHE_ENABLED", "value": True},
        ),
        ActionButton(
            key="clear_metadata_cache",
            label="Clear Metadata Cache",
            description="Clear all cached search results and book details.",
            style="danger",
            callback=_clear_metadata_cache,
        ),
    ]


register_on_save("advanced", _on_save_advanced)
