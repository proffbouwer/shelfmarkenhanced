"""General and search mode settings registration."""

import json
from pathlib import Path

from shelfmark.core.settings_registry import (
    CheckboxField,
    HeadingField,
    MultiSelectField,
    SelectField,
    SettingsField,
    TextField,
    register_settings,
)

# Load supported book languages from data file
# Path is relative to the package root, not this file
_DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"
with (_DATA_DIR / "book-languages.json").open() as _file:
    _SUPPORTED_BOOK_LANGUAGE = json.load(_file)

# Direct mode sort options
_AA_SORT_OPTIONS = [
    {"value": "relevance", "label": "Most relevant"},
    {"value": "newest", "label": "Newest (publication year)"},
    {"value": "oldest", "label": "Oldest (publication year)"},
    {"value": "largest", "label": "Largest (filesize)"},
    {"value": "smallest", "label": "Smallest (filesize)"},
    {"value": "newest_added", "label": "Newest (open sourced)"},
    {"value": "oldest_added", "label": "Oldest (open sourced)"},
]

_FORMAT_OPTIONS = [
    {"value": "epub", "label": "EPUB"},
    {"value": "mobi", "label": "MOBI"},
    {"value": "azw3", "label": "AZW3"},
    {"value": "pdf", "label": "PDF"},
    {"value": "fb2", "label": "FB2"},
    {"value": "djvu", "label": "DJVU"},
    {"value": "cbz", "label": "CBZ"},
    {"value": "cbr", "label": "CBR"},
    {"value": "txt", "label": "TXT"},
    {"value": "rtf", "label": "RTF"},
    {"value": "doc", "label": "DOC"},
    {"value": "docx", "label": "DOCX"},
    {"value": "zip", "label": "ZIP"},
    {"value": "rar", "label": "RAR"},
]

_AUDIOBOOK_FORMAT_OPTIONS = [
    {"value": "m4b", "label": "M4B"},
    {"value": "mp3", "label": "MP3"},
    {"value": "m4a", "label": "M4A"},
    {"value": "zip", "label": "ZIP"},
    {"value": "rar", "label": "RAR"},
]

_LANGUAGE_OPTIONS = [
    {"value": lang["code"], "label": lang["language"]} for lang in _SUPPORTED_BOOK_LANGUAGE
]


def _get_metadata_provider_options() -> list[dict[str, str]]:
    """Build metadata provider options dynamically from enabled providers only."""
    from shelfmark.metadata_providers import is_provider_enabled, list_providers

    options = [
        {"value": provider["name"], "label": provider["display_name"]}
        for provider in list_providers()
        if is_provider_enabled(provider["name"])
    ]

    # If no providers enabled, show a placeholder option
    if not options:
        options = [
            {"value": "", "label": "No providers enabled"},
        ]

    return options


def _get_metadata_provider_options_with_none() -> list[dict[str, str]]:
    """Build metadata provider options with a 'Use main provider' option first."""
    return [{"value": "", "label": "Use book provider"}, *_get_metadata_provider_options()]


def _get_release_source_options_for_content_type(content_type: str) -> list[dict[str, str]]:
    """Build release source options dynamically for a specific content type."""
    from shelfmark.release_sources import list_available_sources

    return [
        {"value": source["name"], "label": source["display_name"]}
        for source in list_available_sources()
        if source.get("enabled", True)
        and source.get("can_be_default", True)
        and content_type in source.get("supported_content_types", ["ebook", "audiobook"])
    ]


def _get_book_release_source_options() -> list[dict[str, str]]:
    """Build default release source options for book searches."""
    return [
        {"value": "", "label": "Use first available source"},
        *_get_release_source_options_for_content_type("ebook"),
    ]


def _get_audiobook_release_source_options() -> list[dict[str, str]]:
    """Build default release source options for audiobook searches."""
    return [
        {"value": "", "label": "Use book release source"},
        *_get_release_source_options_for_content_type("audiobook"),
    ]


def _string_setting(value: object) -> str:
    """Normalize free-form string settings used by select option builders."""
    return value if isinstance(value, str) else str(value or "")


def _clear_covers_cache(current_values: dict) -> dict:
    """Clear the cover image cache."""
    from shelfmark.core.logger import setup_logger

    logger = setup_logger(__name__)

    try:
        from shelfmark.core.image_cache import get_image_cache, reset_image_cache

        cache = get_image_cache()
        count = cache.clear()

        # Reset the singleton so it reinitializes with fresh state
        reset_image_cache()

    except Exception as e:
        logger.exception("Failed to clear cover cache")
        return {
            "success": False,
            "message": f"Failed to clear cache: {e!s}",
        }
    else:
        return {
            "success": True,
            "message": f"Cleared {count} cached cover images.",
        }


def _clear_metadata_cache(current_values: dict) -> dict:
    """Clear the in-memory metadata cache."""
    from shelfmark.core.logger import setup_logger

    logger = setup_logger(__name__)

    try:
        from shelfmark.core.cache import get_metadata_cache

        cache = get_metadata_cache()
        stats_before = cache.stats()
        cache.clear()

        return {
            "success": True,
            "message": f"Cleared {stats_before['size']} cached entries.",
        }
    except Exception as e:
        logger.exception("Failed to clear metadata cache")
        return {
            "success": False,
            "message": f"Failed to clear cache: {e!s}",
        }


@register_settings("general", "General", icon="settings", order=0)
def general_settings() -> list[SettingsField]:
    """Core application settings."""
    return [
        TextField(
            key="SEARCH_PAGE_TITLE",
            label="Search Page Title",
            description="Title shown above the main search box on the homepage.",
            default="Shelfmark",
            placeholder="Shelfmark",
        ),
        TextField(
            key="CALIBRE_WEB_URL",
            label="Library URL",
            description="Adds a navigation button to your book library (Calibre-Web Automated, Grimmory, etc).",
            placeholder="http://calibre-web:8083",
        ),
        TextField(
            key="AUDIOBOOK_LIBRARY_URL",
            label="Audiobook Library URL",
            description="Adds a separate navigation button for your audiobook library (Audiobookshelf, Plex, etc). When both URLs are set, icons are shown instead of text.",
            placeholder="http://audiobookshelf:8080",
        ),
        HeadingField(
            key="search_defaults_heading",
            title="Default Search Filters",
            description="Default filters applied to searches. Can be overridden using advanced search options.",
        ),
        MultiSelectField(
            key="SUPPORTED_FORMATS",
            label="Supported Book Formats",
            description="Book formats to include in search results. ZIP/RAR archives are extracted automatically and book files are used if found.",
            options=_FORMAT_OPTIONS,
            default=["epub", "mobi", "azw3", "fb2", "djvu", "cbz", "cbr"],
        ),
        MultiSelectField(
            key="SUPPORTED_AUDIOBOOK_FORMATS",
            label="Supported Audiobook Formats",
            description="Audiobook formats to include in search results. ZIP/RAR archives are extracted automatically and audiobook files are used if found.",
            options=_AUDIOBOOK_FORMAT_OPTIONS,
            default=["m4b", "mp3"],
        ),
        MultiSelectField(
            key="BOOK_LANGUAGE",
            label="Default Book Languages",
            description="Default language filter for searches.",
            options=_LANGUAGE_OPTIONS,
            default=["en"],
        ),
    ]


@register_settings("search_mode", "Search Mode", icon="search", order=1)
def search_mode_settings() -> list[SettingsField]:
    """Configure how you search for and download books."""
    return [
        HeadingField(
            key="search_mode_heading",
            title="Search Mode",
            description=(
                "Direct mode uses the optional Direct Download source. Universal mode uses "
                "metadata search with whichever release sources you have enabled."
            ),
        ),
        SelectField(
            key="SEARCH_MODE",
            label="Search Mode",
            description="How you want to search for and download books.",
            options=[
                {
                    "value": "direct",
                    "label": "Direct",
                    "description": (
                        "Search with the Direct Download source. Requires enabling the source "
                        "and adding your own mirror URLs."
                    ),
                },
                {
                    "value": "universal",
                    "label": "Universal",
                    "description": "Metadata-based search with downloads from all sources. Book and Audiobook support.",
                },
            ],
            default="universal",
            user_overridable=True,
        ),
        SelectField(
            key="AA_DEFAULT_SORT",
            label="Default Sort Order",
            description="Default sort order for search results.",
            options=_AA_SORT_OPTIONS,
            default="relevance",
            show_when={"field": "SEARCH_MODE", "value": "direct"},
        ),
        CheckboxField(
            key="SHOW_RELEASE_SOURCE_LINKS",
            label="Show Release Source Links",
            description=(
                "Show clickable release-source links in release and details modals. "
                "Metadata provider links stay enabled."
            ),
            default=True,
        ),
        CheckboxField(
            key="SHOW_COMBINED_SELECTOR",
            label="Show Combined Download Selector",
            description="Show the option to search for and download both a book and audiobook together.",
            default=True,
            show_when={"field": "SEARCH_MODE", "value": "universal"},
            user_overridable=True,
        ),
        HeadingField(
            key="universal_mode_heading",
            title="Universal Mode Settings",
            description="Configure metadata providers and release sources for Universal search mode.",
            show_when={"field": "SEARCH_MODE", "value": "universal"},
        ),
        SelectField(
            key="METADATA_PROVIDER",
            label="Book Metadata Provider",
            description="Choose which metadata provider to use for book searches.",
            options=_get_metadata_provider_options,  # Callable - evaluated lazily to avoid circular imports
            default="openlibrary",
            show_when={"field": "SEARCH_MODE", "value": "universal"},
            user_overridable=True,
        ),
        SelectField(
            key="METADATA_PROVIDER_AUDIOBOOK",
            label="Audiobook Metadata Provider",
            description="Metadata provider for audiobook searches. Uses the book provider if not set.",
            options=_get_metadata_provider_options_with_none,  # Callable - includes "Use main provider" option
            default="",
            show_when={"field": "SEARCH_MODE", "value": "universal"},
            user_overridable=True,
        ),
        SelectField(
            key="METADATA_PROVIDER_COMBINED",
            label="Combined Mode Metadata Provider",
            description="Metadata provider for combined mode searches. Uses the book provider if not set.",
            options=_get_metadata_provider_options_with_none,  # Callable - includes "Use main provider" option
            default="",
            show_when={"field": "SEARCH_MODE", "value": "universal"},
            user_overridable=True,
        ),
        SelectField(
            key="DEFAULT_RELEASE_SOURCE",
            label="Default Book Release Source",
            description=(
                "The release source tab to open by default in the release modal for books. "
                "Leave unset to use the first available source."
            ),
            options=_get_book_release_source_options,  # Callable - evaluated lazily to avoid circular imports
            default="",
            show_when={"field": "SEARCH_MODE", "value": "universal"},
            user_overridable=True,
        ),
        SelectField(
            key="DEFAULT_RELEASE_SOURCE_AUDIOBOOK",
            label="Default Audiobook Release Source",
            description="The release source tab to open by default in the release modal for audiobooks. Uses the book release source if not set.",
            options=_get_audiobook_release_source_options,  # Callable - evaluated lazily to avoid circular imports
            default="",
            show_when={"field": "SEARCH_MODE", "value": "universal"},
            user_overridable=True,
        ),
    ]
