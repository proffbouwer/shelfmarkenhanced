"""Settings package for Shelfmark.

Imports all sub-modules to trigger their @register_settings decorators,
and re-exports symbols that external code imports from shelfmark.config.settings.
"""

from pathlib import Path

from shelfmark.config import env
from shelfmark.core.logger import setup_logger
from shelfmark.core.settings_registry import register_group

logger = setup_logger(__name__)

# Log bootstrap configuration values at DEBUG level
logger.debug("Bootstrap configuration:")
for _key in ["CONFIG_DIR", "LOG_DIR", "TMP_DIR", "INGEST_DIR", "DEBUG", "DOCKERMODE"]:
    if hasattr(env, _key):
        logger.debug("  %s: %s", _key, getattr(env, _key))

# Directory settings
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
logger.debug("BASE_DIR: %s", BASE_DIR)
if env.ENABLE_LOGGING:
    env.LOG_DIR.mkdir(exist_ok=True)

# Create staging directory (destination is created by orchestrator using config value)
env.TMP_DIR.mkdir(exist_ok=True)

# DNS placeholders - actual values set by network.init() from config/ENV
CUSTOM_DNS: list[str] = []
DOH_SERVER: str = ""

# Recording directory for debugging internal cloudflare bypasser
RECORDING_DIR = env.LOG_DIR / "recording"

# Register the metadata_providers group (settings populated by separate metadata provider modules)
register_group(
    "metadata_providers",
    "Metadata Providers",
    icon="book",
    order=12,  # Between Network (10) and Advanced (15)
)

# Import all sub-modules to trigger their @register_settings decorators.
# Order matters: general first (defines _SUPPORTED_BOOK_LANGUAGE used by other modules),
# then the rest.
from shelfmark.config.settings import general_settings as _general_settings  # noqa: E402, F401
from shelfmark.config.settings import network_settings as _network_settings  # noqa: E402, F401
from shelfmark.config.settings import download_settings as _download_settings  # noqa: E402, F401
from shelfmark.config.settings import source_settings as _source_settings  # noqa: E402, F401
from shelfmark.config.settings import advanced_settings as _advanced_settings  # noqa: E402, F401

# Re-export public symbols that external code imports from shelfmark.config.settings
from shelfmark.config.settings.general_settings import (  # noqa: E402, F401
    _SUPPORTED_BOOK_LANGUAGE,
    _clear_covers_cache,
    _clear_metadata_cache,
    _get_audiobook_release_source_options,
    _get_book_release_source_options,
    _get_metadata_provider_options,
    _get_metadata_provider_options_with_none,
    _get_release_source_options_for_content_type,
    _string_setting,
    general_settings,
    search_mode_settings,
)
from shelfmark.config.settings.network_settings import network_settings  # noqa: E402, F401
from shelfmark.config.settings.download_settings import (  # noqa: E402, F401
    _contains_path_separators,
    _naming_template_field,
    _on_save_downloads,
    download_settings,
)
from shelfmark.config.settings.source_settings import (  # noqa: E402, F401
    _get_aa_base_url_options,
    _get_fast_source_defaults,
    _get_fast_source_options,
    _get_slow_source_defaults,
    _get_slow_source_options,
    _log_external_bypasser_warning,
    _on_save_mirrors,
    cloudflare_bypass_settings,
    download_source_settings,
    mirror_settings,
)
from shelfmark.config.settings.advanced_settings import (  # noqa: E402, F401
    _on_save_advanced,
    advanced_settings,
)
