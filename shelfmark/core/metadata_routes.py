"""Metadata, release-source, and application-config API routes.

Registers /api/config, /api/health, /api/metadata/*, /api/releases*,
and /api/release-sources/* endpoints.
"""

from __future__ import annotations

import sqlite3
from contextlib import suppress
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable

from flask import Flask, Response, jsonify, request, session

from shelfmark.config.env import BUILD_VERSION, RELEASE_VERSION
from shelfmark.config.settings import _SUPPORTED_BOOK_LANGUAGE
from shelfmark.core.auth_middleware import login_required
from shelfmark.core.config import config as app_config
from shelfmark.core.logger import setup_logger
from shelfmark.core.models import SearchFilters
from shelfmark.core.request_helpers import get_session_db_user_id, normalize_optional_text
from shelfmark.core.request_policy import normalize_source
from shelfmark.release_sources import BrowseRecord, Release, SourceUnavailableError

if TYPE_CHECKING:
    from shelfmark.metadata_providers import BookMetadata, MetadataProvider

logger = setup_logger(__name__)

_OPERATIONAL_ERRORS = (OSError, RuntimeError, TypeError, ValueError, sqlite3.Error)
_IMPORT_OPERATIONAL_ERRORS = (ImportError, *_OPERATIONAL_ERRORS)


def _parse_search_filters_from_request() -> SearchFilters:
    """Parse direct/source browse filters from query parameters."""
    return SearchFilters(
        isbn=request.args.getlist("isbn"),
        author=request.args.getlist("author"),
        title=request.args.getlist("title"),
        lang=request.args.getlist("lang"),
        sort=request.args.get("sort"),
        content=request.args.getlist("content"),
        format=request.args.getlist("format"),
    )


def _build_source_query_book(query_text: str, filters: SearchFilters) -> "BookMetadata":
    """Build a synthetic book context for source-native browse searches."""
    from shelfmark.metadata_providers import BookMetadata

    author_values = [value.strip() for value in (filters.author or []) if str(value).strip()]
    title_values = [value.strip() for value in (filters.title or []) if str(value).strip()]
    isbn_values = [value.strip() for value in (filters.isbn or []) if str(value).strip()]
    title = (
        title_values[0]
        if title_values
        else query_text
        or (isbn_values[0] if isbn_values else "")
        or (author_values[0] if author_values else "Direct Search")
    )
    author = author_values[0] if author_values else ""

    return BookMetadata(
        provider="manual",
        provider_id=query_text or title,
        provider_display_name="Manual Search",
        title=title,
        search_title=title,
        search_author=author or None,
        authors=author_values,
    )


def _serialize_browse_record(record: BrowseRecord) -> dict:
    """Serialize a source-native browse record for the frontend."""
    result = {key: value for key, value in record.__dict__.items() if value is not None}

    preview = result.get("preview")
    if isinstance(preview, str) and preview:
        from shelfmark.core.utils import transform_cover_url

        result["preview"] = transform_cover_url(preview, record.id)

    return result


def _serialize_release(release: Release) -> dict:
    """Serialize a release for the frontend, normalizing preview URLs."""
    from dataclasses import asdict

    from shelfmark.core.utils import transform_cover_url

    result = asdict(release)
    extra = result.get("extra")
    if isinstance(extra, dict):
        preview = extra.get("preview")
        if isinstance(preview, str) and preview:
            extra = dict(extra)
            extra["preview"] = transform_cover_url(preview, release.source_id)
            result["extra"] = extra

    return result


def _resolve_metadata_provider(provider_name: str) -> "MetadataProvider":
    """Validate, instantiate and return a ready metadata provider.

    Raises appropriate HTTP-friendly exceptions on failure.
    """
    from shelfmark.metadata_providers import (
        get_provider,
        get_provider_kwargs,
        is_provider_registered,
    )

    if not is_provider_registered(provider_name):
        msg = f"Unknown metadata provider: {provider_name}"
        raise ValueError(msg)

    kwargs = get_provider_kwargs(provider_name)
    prov = get_provider(provider_name, **kwargs)

    if not prov.is_available():
        msg = f"Provider '{provider_name}' is not available"
        raise RuntimeError(msg)

    return prov


def _handle_target_errors(
    fallback_message: str,
) -> Callable[
    [Callable[..., Response | tuple[Response, int]]], Callable[..., Response | tuple[Response, int]]
]:
    """Wrap a metadata-target route with standard error handling."""

    def decorator(
        fn: Callable[..., Response | tuple[Response, int]],
    ) -> Callable[..., Response | tuple[Response, int]]:
        @wraps(fn)
        def wrapper(*args: object, **kwargs: object) -> Response | tuple[Response, int]:
            try:
                return fn(*args, **kwargs)
            except (NotImplementedError, ValueError) as e:
                return jsonify({"error": str(e)}), 400
            except RuntimeError as e:
                return jsonify({"error": str(e)}), 502
            except (OSError, TypeError, sqlite3.Error) as e:
                logger.error_trace(f"{fallback_message}: {e}")
                return jsonify({"error": fallback_message}), 500

        return wrapper

    return decorator


def register_metadata_routes(app: Flask) -> None:
    """Register metadata, release-source, and application-config routes on the Flask app."""

    @app.route("/api/config", methods=["GET"])
    @login_required
    def api_config() -> Response | tuple[Response, int]:
        """Get application configuration for frontend.

        Uses the dynamic config singleton to ensure settings changes
        are reflected without requiring a container restart.
        """
        try:
            from shelfmark.config.env import _is_config_dir_writable
            from shelfmark.core.onboarding import is_onboarding_complete as _get_onboarding_complete
            from shelfmark.metadata_providers import (
                get_provider_default_sort,
                get_provider_search_fields,
                get_provider_sort_options,
            )

            db_user_id = get_session_db_user_id(session)

            search_mode = app_config.get("SEARCH_MODE", "universal", user_id=db_user_id)
            default_release_source = app_config.get(
                "DEFAULT_RELEASE_SOURCE",
                "",
                user_id=db_user_id,
            )
            default_release_source_audiobook = app_config.get(
                "DEFAULT_RELEASE_SOURCE_AUDIOBOOK",
                "",
                user_id=db_user_id,
            )
            configured_metadata_provider = normalize_optional_text(
                app_config.get(
                    "METADATA_PROVIDER",
                    "",
                    user_id=db_user_id,
                )
            )
            _configured_metadata_provider_audiobook = normalize_optional_text(
                app_config.get(
                    "METADATA_PROVIDER_AUDIOBOOK",
                    "",
                    user_id=db_user_id,
                )
            )
            metadata_ui_provider = (
                configured_metadata_provider or _configured_metadata_provider_audiobook
            )

            config = {
                "calibre_web_url": app_config.get("CALIBRE_WEB_URL", ""),
                "audiobook_library_url": app_config.get("AUDIOBOOK_LIBRARY_URL", ""),
                "search_page_title": app_config.get("SEARCH_PAGE_TITLE", "Shelfmark"),
                "debug": app_config.get("DEBUG", False),
                "build_version": BUILD_VERSION,
                "release_version": RELEASE_VERSION,
                "book_languages": _SUPPORTED_BOOK_LANGUAGE,
                "default_language": app_config.BOOK_LANGUAGE,
                "supported_formats": app_config.SUPPORTED_FORMATS,
                "supported_audiobook_formats": app_config.SUPPORTED_AUDIOBOOK_FORMATS,
                "search_mode": search_mode,
                "metadata_sort_options": get_provider_sort_options(metadata_ui_provider),
                "metadata_search_fields": get_provider_search_fields(metadata_ui_provider),
                "default_release_source": default_release_source,
                "default_release_source_audiobook": default_release_source_audiobook,
                "show_release_source_links": app_config.get("SHOW_RELEASE_SOURCE_LINKS", True),
                "show_combined_selector": app_config.get(
                    "SHOW_COMBINED_SELECTOR", True, user_id=db_user_id
                ),
                "books_output_mode": app_config.get("BOOKS_OUTPUT_MODE", "folder"),
                "auto_open_downloads_sidebar": app_config.get("AUTO_OPEN_DOWNLOADS_SIDEBAR", True),
                "hardcover_auto_remove_on_download": app_config.get(
                    "HARDCOVER_AUTO_REMOVE_ON_DOWNLOAD", True
                ),
                "download_to_browser_content_types": app_config.get(
                    "DOWNLOAD_TO_BROWSER_CONTENT_TYPES",
                    [],
                    user_id=db_user_id,
                ),
                "settings_enabled": _is_config_dir_writable(),
                "onboarding_complete": _get_onboarding_complete(),
                # Default sort orders
                "default_sort": app_config.get(
                    "AA_DEFAULT_SORT", "relevance"
                ),  # For direct mode (Anna's Archive)
                "metadata_default_sort": get_provider_default_sort(
                    metadata_ui_provider
                ),  # For universal mode
            }
            return jsonify(config)
        except _IMPORT_OPERATIONAL_ERRORS as e:
            logger.error_trace(f"Config error: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/health", methods=["GET"])
    def api_health() -> Response | tuple[Response, int]:
        """Health check endpoint for container orchestration.

        No authentication required.

        Returns:
            flask.Response: JSON with status "ok" and optional degraded features.

        """
        from shelfmark.download import orchestrator as backend

        response: dict[str, object] = {"status": "ok"}

        # Report degraded features
        if not backend.WEBSOCKET_AVAILABLE:
            response["degraded"] = {"websocket": "WebSocket unavailable - real-time updates disabled"}

        return jsonify(response)

    @app.route("/api/metadata/providers", methods=["GET"])
    @login_required
    def api_metadata_providers() -> Response | tuple[Response, int]:
        """Get list of available metadata providers.

        Returns:
            flask.Response: JSON with list of providers and their status.

        """
        try:
            from shelfmark.metadata_providers import (
                get_configured_provider_name,
                get_provider,
                get_provider_kwargs,
                list_providers,
            )

            app_config.refresh()
            db_user_id = get_session_db_user_id(session)

            configured_metadata_provider = get_configured_provider_name(
                content_type="ebook",
                user_id=db_user_id,
                fallback_to_main=True,
            )
            configured_audiobook_metadata_provider = get_configured_provider_name(
                content_type="audiobook",
                user_id=db_user_id,
                fallback_to_main=False,
            )
            configured_combined_metadata_provider = get_configured_provider_name(
                content_type="combined",
                user_id=db_user_id,
                fallback_to_main=False,
            )
            providers = []
            for info in list_providers():
                enabled_key = f"{info['name'].upper()}_ENABLED"
                provider_info = {
                    "name": info["name"],
                    "display_name": info["display_name"],
                    "requires_auth": info["requires_auth"],
                    "enabled": app_config.get(enabled_key, False) is True,
                    "available": False,
                }

                try:
                    kwargs = get_provider_kwargs(info["name"])
                    provider = get_provider(info["name"], **kwargs)
                    provider_info["available"] = provider.is_available()
                except _OPERATIONAL_ERRORS as exc:
                    logger.debug(
                        "Metadata provider %s availability check failed: %s",
                        info["name"],
                        exc,
                    )

                providers.append(provider_info)

            return jsonify(
                {
                    "providers": providers,
                    "configured_provider": configured_metadata_provider or None,
                    "configured_provider_audiobook": configured_audiobook_metadata_provider or None,
                    "configured_provider_combined": configured_combined_metadata_provider or None,
                }
            )
        except _IMPORT_OPERATIONAL_ERRORS as e:
            logger.error_trace(f"Metadata providers error: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/metadata/config", methods=["GET"])
    @login_required
    def api_metadata_config() -> Response | tuple[Response, int]:
        """Return provider-specific metadata search config for the active session."""
        try:
            from shelfmark.metadata_providers import (
                get_configured_provider_name,
                get_provider,
                get_provider_capabilities,
                get_provider_default_sort,
                get_provider_kwargs,
                get_provider_search_fields,
                get_provider_sort_options,
                is_provider_registered,
            )

            app_config.refresh()
            content_type = request.args.get("content_type", "ebook").strip()
            provider_name = request.args.get("provider", "").strip()

            db_user_id = get_session_db_user_id(session)

            if not provider_name:
                provider_name = get_configured_provider_name(
                    content_type=content_type,
                    user_id=db_user_id,
                    fallback_to_main=True,
                )

            if not provider_name:
                return jsonify(
                    {
                        "provider": None,
                        "display_name": None,
                        "enabled": False,
                        "available": False,
                        "search_fields": [],
                        "capabilities": [],
                        "sort_options": [{"value": "relevance", "label": "Most relevant"}],
                        "default_sort": "relevance",
                    }
                )

            if not is_provider_registered(provider_name):
                return jsonify({"error": f"Unknown metadata provider: {provider_name}"}), 400

            kwargs = get_provider_kwargs(provider_name)
            provider = get_provider(provider_name, **kwargs)
            enabled_key = f"{provider_name.upper()}_ENABLED"
            provider_enabled = app_config.get(enabled_key, False) is True
            provider_available = provider.is_available()

            return jsonify(
                {
                    "provider": provider_name,
                    "display_name": provider.display_name,
                    "enabled": provider_enabled,
                    "available": provider_available,
                    "search_fields": get_provider_search_fields(provider_name),
                    "capabilities": get_provider_capabilities(provider_name),
                    "sort_options": get_provider_sort_options(provider_name),
                    "default_sort": get_provider_default_sort(provider_name, user_id=db_user_id),
                }
            )
        except _IMPORT_OPERATIONAL_ERRORS as e:
            logger.error_trace(f"Metadata config error: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/metadata/search", methods=["GET"])
    @login_required
    def api_metadata_search() -> Response | tuple[Response, int]:
        """Search for books using the configured metadata provider.

        Query Parameters:
            query (str): Search query (required)
            limit (int): Maximum number of results (default: 40, max: 100)
            sort (str): Sort order - relevance, popularity, rating, newest, oldest (default: relevance)
            [dynamic fields]: Provider-specific search fields passed as query params

        Returns:
            flask.Response: JSON with list of books from metadata provider.

        """
        try:
            from dataclasses import asdict

            from shelfmark.metadata_providers import (
                CheckboxSearchField,
                MetadataSearchOptions,
                NumberSearchField,
                SortOrder,
                get_configured_provider,
                get_provider,
                get_provider_kwargs,
                is_provider_enabled,
                is_provider_registered,
            )

            query = request.args.get("query", "").strip()
            content_type = request.args.get("content_type", "ebook").strip()
            provider_name = request.args.get("provider", "").strip()

            try:
                limit = min(int(request.args.get("limit", 40)), 100)
            except ValueError:
                limit = 40

            try:
                page = max(1, int(request.args.get("page", 1)))
            except ValueError:
                page = 1

            # Parse sort parameter
            sort_value = request.args.get("sort", "relevance").lower()
            try:
                sort_order = SortOrder(sort_value)
            except ValueError:
                sort_order = SortOrder.RELEVANCE

            db_user_id = get_session_db_user_id(session)

            if provider_name:
                if not is_provider_registered(provider_name):
                    return jsonify(
                        {
                            "error": f"Unknown metadata provider: {provider_name}",
                            "message": f"Unknown metadata provider: {provider_name}",
                        }
                    ), 400
                if not is_provider_enabled(provider_name):
                    return jsonify(
                        {
                            "error": f"Metadata provider '{provider_name}' is not enabled",
                            "message": f"{provider_name} is not enabled. Enable it in Settings first.",
                        }
                    ), 503

                kwargs = get_provider_kwargs(provider_name)
                provider = get_provider(provider_name, **kwargs)
            else:
                provider = get_configured_provider(content_type=content_type, user_id=db_user_id)

            if not provider:
                return jsonify(
                    {
                        "error": "No metadata provider configured",
                        "message": "No metadata provider configured. Enable one in Settings.",
                    }
                ), 503

            if not provider.is_available():
                return jsonify(
                    {
                        "error": f"Metadata provider '{provider.name}' is not available",
                        "message": f"{provider.display_name} is not available. Check configuration in Settings.",
                    }
                ), 503

            # Extract custom search field values from query params
            fields: dict[str, Any] = {}
            for search_field in provider.search_fields:
                value = request.args.get(search_field.key)
                if value is not None:
                    # Strip string values to handle whitespace-only input
                    value = value.strip()
                    if value != "":
                        # Parse value based on field type
                        if isinstance(search_field, CheckboxSearchField):
                            fields[search_field.key] = value.lower() in ("true", "1", "yes", "on")
                        elif isinstance(search_field, NumberSearchField):
                            with suppress(ValueError):
                                fields[search_field.key] = int(value)
                        else:
                            fields[search_field.key] = value

            # Require either a query or at least one field value
            if not query and not fields:
                return jsonify({"error": "Either 'query' or search field values are required"}), 400

            options = MetadataSearchOptions(
                query=query, limit=limit, page=page, sort=sort_order, fields=fields
            )
            search_result = provider.search_paginated(options)

            # Convert BookMetadata objects to dicts
            books_data = [asdict(book) for book in search_result.books]

            # Transform cover_url to local proxy URLs when caching is enabled
            from shelfmark.core.utils import transform_cover_url

            for book_dict in books_data:
                if book_dict.get("cover_url"):
                    cache_id = f"{book_dict['provider']}_{book_dict['provider_id']}"
                    book_dict["cover_url"] = transform_cover_url(book_dict["cover_url"], cache_id)

            response_data = {
                "books": books_data,
                "provider": provider.name,
                "query": query,
                "page": search_result.page,
                "total_found": search_result.total_found,
                "has_more": search_result.has_more,
            }
            if search_result.source_url:
                response_data["source_url"] = search_result.source_url
            if search_result.source_title:
                response_data["source_title"] = search_result.source_title
            return jsonify(response_data)
        except _IMPORT_OPERATIONAL_ERRORS as e:
            logger.error_trace(f"Metadata search error: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/metadata/field-options", methods=["GET"])
    @login_required
    def api_metadata_field_options() -> Response:
        """Return dynamic search-field options for a metadata provider."""
        try:
            from shelfmark.metadata_providers import (
                get_configured_provider,
                get_provider,
                get_provider_kwargs,
                is_provider_registered,
            )

            field_key = request.args.get("field", "").strip()
            provider_name = request.args.get("provider", "").strip()
            content_type = request.args.get("content_type", "ebook").strip()
            query_text = request.args.get("query", "").strip()

            if not field_key:
                return jsonify({"options": []})

            db_user_id = get_session_db_user_id(session)

            provider = None
            if provider_name:
                if not is_provider_registered(provider_name):
                    return jsonify({"options": []})
                kwargs = get_provider_kwargs(provider_name)
                provider = get_provider(provider_name, **kwargs)
            else:
                provider = get_configured_provider(content_type=content_type, user_id=db_user_id)

            if not provider or not provider.is_available():
                return jsonify({"options": []})

            options = provider.get_search_field_options(field_key, query=query_text or None)
            return jsonify({"options": options})
        except _OPERATIONAL_ERRORS as e:
            logger.warning("Metadata field options endpoint error: %s", e)
            return jsonify({"options": []})

    @app.route("/api/metadata/book/<provider>/<book_id>", methods=["GET"])
    @login_required
    def api_metadata_book(provider: str, book_id: str) -> Response | tuple[Response, int]:
        """Get detailed book information from a metadata provider.

        Path Parameters:
            provider (str): Provider name (e.g., "hardcover", "openlibrary")
            book_id (str): Book ID in the provider's system

        Returns:
            flask.Response: JSON with book details.

        """
        try:
            from dataclasses import asdict

            prov = _resolve_metadata_provider(provider)

            book = prov.get_book(book_id)
            if not book:
                return jsonify({"error": "Book not found"}), 404

            book_dict = asdict(book)

            # Transform cover_url to local proxy URL when caching is enabled
            from shelfmark.core.utils import transform_cover_url

            if book_dict.get("cover_url"):
                cache_id = f"{provider}_{book_id}"
                book_dict["cover_url"] = transform_cover_url(book_dict["cover_url"], cache_id)

            return jsonify(book_dict)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except RuntimeError as e:
            return jsonify({"error": str(e)}), 503
        except (OSError, TypeError, sqlite3.Error) as e:
            logger.error_trace(f"Metadata book error: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/metadata/book/<provider>/<book_id>/targets", methods=["GET"])
    @login_required
    @_handle_target_errors("Failed to load book targets")
    def api_metadata_book_targets(provider: str, book_id: str) -> Response | tuple[Response, int]:
        """Get provider-managed list/status targets for a specific book."""
        prov = _resolve_metadata_provider(provider)
        return jsonify({"options": prov.get_book_targets(book_id)})

    @app.route("/api/metadata/book/<provider>/targets/batch", methods=["POST"])
    @login_required
    @_handle_target_errors("Failed to load book targets")
    def api_metadata_book_targets_batch(provider: str) -> Response | tuple[Response, int]:
        """Get provider-managed list/status targets for multiple books."""
        prov = _resolve_metadata_provider(provider)

        payload = request.get_json(silent=True) or {}
        raw_ids = payload.get("book_ids", []) if isinstance(payload, dict) else []
        if not isinstance(raw_ids, list) or not raw_ids:
            return jsonify({"error": "book_ids must be a non-empty array"}), 400

        book_ids = [str(bid) for bid in raw_ids[:50]]

        return jsonify({"results": prov.get_book_targets_batch(book_ids)})

    @app.route("/api/metadata/book/<provider>/<book_id>/targets", methods=["PUT"])
    @login_required
    @_handle_target_errors("Failed to update book targets")
    def api_metadata_book_targets_update(
        provider: str, book_id: str
    ) -> Response | tuple[Response, int]:
        """Set whether a book belongs to a provider-managed list or shelf."""
        prov = _resolve_metadata_provider(provider)

        payload = request.get_json(silent=True) or {}
        target = str(payload.get("target", "")).strip() if isinstance(payload, dict) else ""
        selected = payload.get("selected") if isinstance(payload, dict) else None
        if not target:
            return jsonify({"error": "target is required"}), 400
        if not isinstance(selected, bool):
            return jsonify({"error": "selected must be a boolean"}), 400

        result = prov.set_book_target_state(book_id, target, selected=selected)
        response: dict = {
            "success": True,
            "changed": bool(result.get("changed", True)),
            "selected": selected,
        }
        deselected = result.get("deselected_target")
        if isinstance(deselected, str) and deselected:
            response["deselected_target"] = deselected
        return jsonify(response)

    @app.route("/api/releases", methods=["GET"])
    @login_required
    def api_releases() -> Response | tuple[Response, int]:
        """Search for downloadable releases of a book.

        This endpoint takes book metadata and searches available release sources
        (e.g., Anna's Archive, Libgen) for downloadable files.

        Query Parameters:
            provider (str): Metadata provider name (required)
            book_id (str): Book ID from metadata provider (required)
            source (str): Release source to search (optional, default: all)

        Returns:
            flask.Response: JSON with list of available releases.

        """
        try:
            from dataclasses import asdict

            from shelfmark.core.search_plan import build_release_search_plan
            from shelfmark.metadata_providers import (
                BookMetadata,
                get_provider,
                get_provider_kwargs,
                is_provider_registered,
            )
            from shelfmark.release_sources import (
                browse_record_to_book_metadata,
                get_source,
                list_available_sources,
                serialize_column_config,
                source_results_are_releases,
            )

            def _search_source_releases(
                source_name: str, search_book: BookMetadata
            ) -> tuple[Any | None, list[Any], str | None]:
                """Search one source and return any error message instead of raising."""
                try:
                    source = get_source(source_name)

                    plan = build_release_search_plan(
                        search_book,
                        languages=browse_filters.lang
                        if source_query_filters is not None
                        else languages,
                        manual_query=query_text if source_query_filters is not None else manual_query,
                        indexers=indexers,
                        source_filters=source_query_filters,
                    )

                    if plan.source_filters is not None:
                        planned_query = plan.manual_query or plan.primary_query
                        planned_query_type = "query"
                    elif plan.manual_query:
                        planned_query = plan.manual_query
                        planned_query_type = "manual"
                    elif not expand_search and plan.isbn_candidates:
                        planned_query = plan.isbn_candidates[0]
                        planned_query_type = "isbn"
                    else:
                        planned_query = plan.primary_query
                        planned_query_type = "title_author"

                    logger.debug(
                        "Searching %s: %s='%s' (title='%s', authors=%s, expand=%s, content_type=%s)",
                        source_name,
                        planned_query_type,
                        planned_query,
                        search_book.title,
                        search_book.authors,
                        expand_search,
                        content_type,
                    )

                    releases = source.search(
                        search_book, plan, expand_search=expand_search, content_type=content_type
                    )
                except ValueError:
                    return None, [], f"Unknown source: {source_name}"
                except (SourceUnavailableError, *_OPERATIONAL_ERRORS) as e:
                    logger.warning("Release search failed for source %s: %s", source_name, e)
                    return None, [], f"{source_name}: {e!s}"
                else:
                    return source, releases, None

            provider = request.args.get("provider", "").strip()
            book_id = request.args.get("book_id", "").strip()
            source_filter = request.args.get("source", "").strip()
            query_text = request.args.get("query", "").strip()
            # Accept title/author from frontend to avoid re-fetching metadata
            title_param = request.args.get("title", "").strip()
            author_param = request.args.get("author", "").strip()
            expand_search = request.args.get("expand_search", "").lower() == "true"
            # Accept language codes for filtering (comma-separated)
            languages_param = request.args.get("languages", "").strip()
            languages = (
                [lang.strip() for lang in languages_param.split(",") if lang.strip()]
                if languages_param
                else None
            )
            # Content type for audiobook vs ebook search
            content_type = request.args.get("content_type", "ebook").strip()

            manual_query = request.args.get("manual_query", "").strip()

            # Accept indexer names for Prowlarr filtering (comma-separated)
            indexers_param = request.args.get("indexers", "").strip()
            indexers = (
                [idx.strip() for idx in indexers_param.split(",") if idx.strip()]
                if indexers_param
                else None
            )
            browse_filters = _parse_search_filters_from_request()
            has_browse_filters = bool(query_text or any(vars(browse_filters).values()))

            source_query_filters = None
            is_source_provider = bool(provider) and source_results_are_releases(provider)

            book: BookMetadata

            if not provider or not book_id:
                if not source_filter or not has_browse_filters:
                    return jsonify({"error": "Parameters 'provider' and 'book_id' are required"}), 400
                if not source_results_are_releases(source_filter):
                    return jsonify(
                        {"error": f"Source does not support browse release search: {source_filter}"}
                    ), 400

                book = _build_source_query_book(query_text, browse_filters)
                source_query_filters = browse_filters
            elif is_source_provider:
                # Source-backed browse flows can reopen the release modal with provider=<source name>.
                # In that flow, treat the source-native record as release-search context instead of
                # requiring a metadata provider registration.
                source = get_source(provider)
                direct_record = source.get_record(book_id)
                if direct_record is None:
                    return jsonify({"error": "Book not found in release source"}), 404

                book = browse_record_to_book_metadata(
                    direct_record,
                    title_override=title_param or None,
                    author_override=author_param or None,
                )
            elif provider == "manual":
                resolved_title = title_param or manual_query or "Manual Search"
                resolved_author = author_param or ""
                authors = [a.strip() for a in resolved_author.split(",") if a.strip()]

                book = BookMetadata(
                    provider="manual",
                    provider_id=book_id,
                    provider_display_name="Manual Search",
                    title=resolved_title,
                    search_title=resolved_title,
                    search_author=resolved_author or None,
                    authors=authors,
                )
            else:
                if not is_provider_registered(provider):
                    return jsonify({"error": f"Unknown metadata provider: {provider}"}), 400

                # Get book metadata from provider
                kwargs = get_provider_kwargs(provider)
                prov = get_provider(provider, **kwargs)
                resolved_book = prov.get_book(book_id)

                if not resolved_book:
                    return jsonify({"error": "Book not found in metadata provider"}), 404
                book = resolved_book

                # Override title from frontend if available (search results may have better data)
                # Note: We intentionally DON'T override authors here - get_book() now returns
                # filtered authors (primary authors only, excluding translators/narrators),
                # which gives better release search results than the unfiltered search data
                if title_param:
                    book.title = title_param

            # Determine which release sources to search
            if source_query_filters is not None or source_filter:
                sources_to_search = [source_filter]
            elif is_source_provider:
                # Source-backed browse flows stay within the source that produced the record.
                sources_to_search = [provider]
            else:
                # Search only enabled sources
                sources_to_search = [src["name"] for src in list_available_sources() if src["enabled"]]

            # Search each source for releases
            all_releases = []
            errors = []
            source_instances = {}  # Keep source instances for column config

            for source_name in sources_to_search:
                source, releases, error = _search_source_releases(source_name, book)
                if source is not None:
                    source_instances[source_name] = source
                    all_releases.extend(releases)
                if error is not None:
                    errors.append(error)

            # Convert Release objects to dicts
            releases_data = [_serialize_release(release) for release in all_releases]

            # Get column config from the first source searched
            # Reuse the same instance to get any dynamic data (e.g., online_servers for IRC)
            column_config = None
            if sources_to_search and sources_to_search[0] in source_instances:
                try:
                    first_source = source_instances[sources_to_search[0]]
                    column_config = serialize_column_config(first_source.get_column_config())
                except _OPERATIONAL_ERRORS as e:
                    logger.warning("Failed to get column config: %s", e)

            # Convert book to dict and transform cover_url
            book_dict = asdict(book)
            from shelfmark.core.utils import transform_cover_url

            if book_dict.get("cover_url"):
                cache_id = f"{provider}_{book_id}"
                book_dict["cover_url"] = transform_cover_url(book_dict["cover_url"], cache_id)

            search_info = {}
            for source_name, source_instance in source_instances.items():
                if hasattr(source_instance, "last_search_type") and source_instance.last_search_type:
                    search_info[source_name] = {"search_type": source_instance.last_search_type}

            response = {
                "releases": releases_data,
                "book": book_dict,
                "sources_searched": sources_to_search,
                "column_config": column_config,
                "search_info": search_info,
            }

            if errors:
                response["errors"] = errors

            # If no releases found and there were errors, return 503 with the first
            # source failure message so direct-mode source query searches surface the
            # same unavailable-state messaging as release modal searches.
            if not releases_data and errors:
                # Use the first error message (typically the most relevant)
                error_message = errors[0]
                # Strip the source prefix if present (e.g., "direct_download: message" -> "message")
                if ": " in error_message:
                    error_message = error_message.split(": ", 1)[1]
                return jsonify({"error": error_message}), 503

            return jsonify(response)
        except SourceUnavailableError as e:
            logger.warning("Release search unavailable: %s", e)
            return jsonify({"error": str(e)}), 503
        except _IMPORT_OPERATIONAL_ERRORS as e:
            logger.error_trace(f"Releases search error: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/release-sources", methods=["GET"])
    @login_required
    def api_release_sources() -> Response | tuple[Response, int]:
        """Get available release sources from the plugin registry.

        Returns:
            flask.Response: JSON list of available release sources.

        """
        try:
            from shelfmark.release_sources import list_available_sources

            sources = list_available_sources()
            return jsonify(sources)
        except _IMPORT_OPERATIONAL_ERRORS as e:
            logger.error_trace(f"Release sources error: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/release-sources/<source_name>/records/<path:record_id>", methods=["GET"])
    @login_required
    def api_release_source_record(source_name: str, record_id: str) -> Response | tuple[Response, int]:
        """Resolve a source-native browse record for a release source."""
        try:
            from shelfmark.release_sources import get_source

            source = get_source(source_name)
            record = source.get_record(record_id)
            if record is None:
                return jsonify({"error": "Record not found"}), 404
            return jsonify(_serialize_browse_record(record))
        except ValueError:
            return jsonify({"error": f"Unknown release source: {source_name}"}), 400
        except SourceUnavailableError as e:
            logger.warning("Release source record unavailable: %s", e)
            return jsonify({"error": str(e)}), 503
        except _OPERATIONAL_ERRORS as e:
            logger.error_trace(f"Release source record error: {e}")
            return jsonify({"error": str(e)}), 500
