"""Download settings registration."""

from typing import Any

from shelfmark.config.booklore_settings import (
    check_booklore_connection,
    get_booklore_library_options,
    get_booklore_path_options,
)
from shelfmark.config.download_settings_handlers import (
    check_audiobook_destination,
    check_books_destination,
)
from shelfmark.config.email_settings import check_email_connection
from shelfmark.core.settings_registry import (
    ActionButton,
    CheckboxField,
    CustomComponentField,
    HeadingField,
    MultiSelectField,
    NumberField,
    OrderableListField,
    PasswordField,
    SelectField,
    SettingsField,
    TableField,
    TagListField,
    TextField,
    load_config_file,
    register_on_save,
    register_settings,
)

_SMTP_PORT_MAX = 65535
_EMAIL_ATTACHMENT_LIMIT_MB_MAX = 600

_DOWNLOAD_TO_BROWSER_CONTENT_TYPE_OPTIONS = [
    {
        "value": "book",
        "label": "Books",
        "description": "Automatically download completed book files to this browser.",
    },
    {
        "value": "audiobook",
        "label": "Audiobooks",
        "description": "Automatically download completed audiobook files to this browser.",
    },
]

_DOWNLOAD_TO_BROWSER_CONTENT_TYPE_VALUES = {
    option["value"] for option in _DOWNLOAD_TO_BROWSER_CONTENT_TYPE_OPTIONS
}


def _contains_path_separators(value: Any) -> bool:
    return isinstance(value, str) and ("/" in value or "\\" in value)


def _on_save_downloads(values: dict[str, Any]) -> dict[str, Any]:
    """Validate download settings before persisting."""
    existing = load_config_file("downloads")
    effective: dict[str, Any] = dict(existing)
    effective.update(values)

    if "DOWNLOAD_TO_BROWSER_CONTENT_TYPES" in effective:
        raw_content_types = effective.get("DOWNLOAD_TO_BROWSER_CONTENT_TYPES")
        if raw_content_types is None:
            normalized_content_types: list[str] = []
        elif isinstance(raw_content_types, list):
            normalized_content_types = [
                str(value).strip().lower() for value in raw_content_types if str(value).strip()
            ]
        else:
            return {
                "error": True,
                "message": "Download to Browser must be a list.",
                "values": values,
            }

        deduped_content_types: list[str] = []
        for content_type in normalized_content_types:
            if content_type not in _DOWNLOAD_TO_BROWSER_CONTENT_TYPE_VALUES:
                allowed = ", ".join(sorted(_DOWNLOAD_TO_BROWSER_CONTENT_TYPE_VALUES))
                return {
                    "error": True,
                    "message": (
                        "Download to Browser contains an unsupported content type "
                        f"'{content_type}'. Supported values: {allowed}"
                    ),
                    "values": values,
                }
            if content_type not in deduped_content_types:
                deduped_content_types.append(content_type)

        values["DOWNLOAD_TO_BROWSER_CONTENT_TYPES"] = deduped_content_types
        effective["DOWNLOAD_TO_BROWSER_CONTENT_TYPES"] = deduped_content_types

    # Books: only validate templates when saving to a folder.
    books_output_mode = effective.get("BOOKS_OUTPUT_MODE", "folder")
    if books_output_mode == "folder" and effective.get("FILE_ORGANIZATION", "rename") == "rename":
        template = effective.get("TEMPLATE_RENAME", "")
        if _contains_path_separators(template):
            return {
                "error": True,
                "message": "Books Naming Template cannot contain '/' or '\\' in Rename mode. Use Organize mode to create folders.",
                "values": values,
            }

    # Audiobooks are always folder output.
    if effective.get("FILE_ORGANIZATION_AUDIOBOOK", "rename") == "rename":
        template = effective.get("TEMPLATE_AUDIOBOOK_RENAME", "")
        if _contains_path_separators(template):
            return {
                "error": True,
                "message": "Audiobooks Naming Template cannot contain '/' or '\\' in Rename mode. Use Organize mode to create folders.",
                "values": values,
            }

    # Email output (SMTP) validation.
    if books_output_mode == "email":
        from email.utils import parseaddr

        def _is_plain_email_address(addr: str) -> bool:
            parsed = parseaddr(addr or "")[1]
            return bool(parsed) and "@" in parsed and parsed == addr

        # Preferred model: single recipient for global default and per-user override.
        raw_recipient = str(effective.get("EMAIL_RECIPIENT", "") or "").strip()

        # Optional global fallback: validate only when a default recipient is provided.
        if raw_recipient and not _is_plain_email_address(raw_recipient):
            return {
                "error": True,
                "message": "Email recipient must be a valid plain email address.",
                "values": values,
            }

        smtp_host = str(effective.get("EMAIL_SMTP_HOST", "") or "").strip()
        if not smtp_host:
            return {"error": True, "message": "SMTP host is required", "values": values}

        security = str(effective.get("EMAIL_SMTP_SECURITY", "starttls") or "").strip().lower()
        if security not in {"none", "starttls", "ssl"}:
            return {
                "error": True,
                "message": "SMTP security must be one of: none, starttls, ssl",
                "values": values,
            }

        try:
            port = int(effective.get("EMAIL_SMTP_PORT", 587))
        except (TypeError, ValueError):
            return {"error": True, "message": "SMTP port must be a number", "values": values}

        if port < 1 or port > _SMTP_PORT_MAX:
            return {
                "error": True,
                "message": f"SMTP port must be between 1 and {_SMTP_PORT_MAX}",
                "values": values,
            }

        try:
            timeout_seconds = int(effective.get("EMAIL_SMTP_TIMEOUT_SECONDS", 60))
        except (TypeError, ValueError):
            return {
                "error": True,
                "message": "SMTP timeout (seconds) must be a number",
                "values": values,
            }

        if timeout_seconds < 1:
            return {
                "error": True,
                "message": "SMTP timeout (seconds) must be >= 1",
                "values": values,
            }

        username = str(effective.get("EMAIL_SMTP_USERNAME", "") or "").strip()
        password = effective.get("EMAIL_SMTP_PASSWORD", "") or ""
        if username and not password:
            return {
                "error": True,
                "message": "SMTP password is required when username is set",
                "values": values,
            }

        try:
            attachment_limit_mb = int(effective.get("EMAIL_ATTACHMENT_SIZE_LIMIT_MB", 25))
        except (TypeError, ValueError):
            return {
                "error": True,
                "message": "Attachment size limit (MB) must be a number",
                "values": values,
            }

        if attachment_limit_mb < 1 or attachment_limit_mb > _EMAIL_ATTACHMENT_LIMIT_MB_MAX:
            return {
                "error": True,
                "message": (
                    "Attachment size limit (MB) must be between 1 and "
                    f"{_EMAIL_ATTACHMENT_LIMIT_MB_MAX}"
                ),
                "values": values,
            }

        from_addr = str(effective.get("EMAIL_FROM", "") or "").strip()
        if not from_addr:
            # If From is empty, default to the SMTP username when it looks like an email address.
            username_email = parseaddr(username)[1]
            if username_email and "@" in username_email:
                from_addr = f"Shelfmark <{username_email}>"
                values["EMAIL_FROM"] = from_addr
            else:
                return {
                    "error": True,
                    "message": "From address is required (or set SMTP username to an email address).",
                    "values": values,
                }
        else:
            from_email = parseaddr(from_addr)[1]
            if not from_email or "@" not in from_email:
                return {
                    "error": True,
                    "message": "From address must be a valid email address",
                    "values": values,
                }

        # Persist any normalization/coercion for fields that may have been edited this save.
        if "EMAIL_RECIPIENT" in values:
            values["EMAIL_RECIPIENT"] = raw_recipient
        if "EMAIL_SMTP_SECURITY" in values:
            values["EMAIL_SMTP_SECURITY"] = security
        if "EMAIL_SMTP_PORT" in values:
            values["EMAIL_SMTP_PORT"] = port
        if "EMAIL_SMTP_TIMEOUT_SECONDS" in values:
            values["EMAIL_SMTP_TIMEOUT_SECONDS"] = timeout_seconds
        if "EMAIL_ATTACHMENT_SIZE_LIMIT_MB" in values:
            values["EMAIL_ATTACHMENT_SIZE_LIMIT_MB"] = attachment_limit_mb

    return {"error": False, "values": values}


def _naming_template_field(
    *,
    key: str,
    label: str,
    description: str,
    default: str,
    placeholder: str,
    show_when: dict[str, Any] | list[dict[str, Any]],
    universal_only: bool = False,
) -> CustomComponentField:
    return CustomComponentField(
        key=f"{key.lower()}_editor",
        label=label,
        component="naming_template",
        show_when=show_when,
        universal_only=universal_only,
        wrap_in_field_wrapper=True,
        value_fields=[
            TextField(
                key=key,
                label=label,
                description=description,
                default=default,
                placeholder=placeholder,
                show_when=show_when,
                universal_only=universal_only,
            )
        ],
    )


@register_settings("downloads", "Downloads", icon="folder", order=5)
def download_settings() -> list[SettingsField]:
    """Configure download behavior and file locations."""
    return [
        # === BOOKS SECTION ===
        # Visible for ALL modes (Direct + Universal)
        HeadingField(
            key="books_heading",
            title="Books",
            description="Configure where ebooks, comics, and magazines are saved.",
        ),
        SelectField(
            key="BOOKS_OUTPUT_MODE",
            label="Output Mode",
            description="Choose where completed book files are sent.",
            options=[
                {
                    "value": "folder",
                    "label": "Folder",
                    "description": "Save files to the destination folder",
                },
                {
                    "value": "email",
                    "label": "Email (SMTP)",
                    "description": "Send files as an email attachment",
                },
                {
                    "value": "booklore",
                    "label": "Grimmory (API)",
                    "description": "Upload files directly to Grimmory",
                },
            ],
            default="folder",
            user_overridable=True,
        ),
        TextField(
            key="DESTINATION",
            label="Destination",
            description="Directory where downloaded files are saved. Use {User} for per-user folders (e.g. /books/{User}).",
            default="/books",
            required=True,
            env_var="INGEST_DIR",  # Legacy env var name for backwards compatibility
            user_overridable=True,
            show_when={
                "field": "BOOKS_OUTPUT_MODE",
                "value": "folder",
            },
        ),
        ActionButton(
            key="test_destination",
            label="Test Destination",
            description="Check that Shelfmark can create and write to this destination.",
            style="primary",
            callback=check_books_destination,
            show_when={
                "field": "BOOKS_OUTPUT_MODE",
                "value": "folder",
            },
        ),
        SelectField(
            key="FILE_ORGANIZATION",
            label="File Organization",
            description="Choose how downloaded book files are named and organized.",
            options=[
                {
                    "value": "none",
                    "label": "None",
                    "description": "Keep original filename from source",
                },
                {
                    "value": "rename",
                    "label": "Rename Only",
                    "description": "Rename single-file downloads; multi-file keeps original names.",
                },
                {
                    "value": "organize",
                    "label": "Rename and Organize",
                    "description": "Create folders and rename files using a template. Do not use with ingest folders.",
                },
            ],
            default="rename",
            show_when={
                "field": "BOOKS_OUTPUT_MODE",
                "value": "folder",
            },
        ),
        # Rename mode template - filename only
        _naming_template_field(
            key="TEMPLATE_RENAME",
            label="Naming Template",
            description=(
                "Variables: {Author}, {Title}, {Year}, {User}, {OriginalName} "
                "(source filename without extension). Universal adds: {Series}, "
                "{SeriesPosition}, {Subtitle}, {PrimaryTitle}. Use arbitrary prefix/suffix: "
                "{Vol. SeriesPosition - } outputs 'Vol. 2 - ' when set, nothing when empty. "
                "Rename templates are filename-only (no '/' or '\\'); use Organize for folders. "
                "Applies to single-file downloads."
            ),
            default="{Author} - {Title} ({Year})",
            placeholder="{Author} - {Title} ({Year})",
            show_when=[
                {"field": "BOOKS_OUTPUT_MODE", "value": "folder"},
                {"field": "FILE_ORGANIZATION", "value": "rename"},
            ],
        ),
        # Organize mode template - folders allowed
        _naming_template_field(
            key="TEMPLATE_ORGANIZE",
            label="Path Template",
            description=(
                "Use / to create folders. Variables: {Author}, {Title}, {Year}, {User}, "
                "{OriginalName} (source filename without extension). Universal adds: {Series}, "
                "{SeriesPosition}, {Subtitle}, {PrimaryTitle}. Use arbitrary prefix/suffix: "
                "{Vol. SeriesPosition - } outputs 'Vol. 2 - ' when set, nothing when empty."
            ),
            default="{Author}/{Title} ({Year})",
            placeholder="{Author}/{Series/}{Title} ({Year})",
            show_when=[
                {"field": "BOOKS_OUTPUT_MODE", "value": "folder"},
                {"field": "FILE_ORGANIZATION", "value": "organize"},
            ],
        ),
        CheckboxField(
            key="HARDLINK_TORRENTS",
            label="Hardlink Book Torrents",
            description="Create hardlinks instead of copying. Preserves seeding but archives won't be extracted. Don't use if destination is a library ingest folder.",
            default=False,
            universal_only=True,
            show_when={
                "field": "BOOKS_OUTPUT_MODE",
                "value": "folder",
            },
        ),
        HeadingField(
            key="booklore_heading",
            title="Grimmory",
            description="Upload books directly to Grimmory (Formerly Booklore) via API. Audiobooks always use folder mode.",
            show_when={"field": "BOOKS_OUTPUT_MODE", "value": "booklore"},
        ),
        TextField(
            key="BOOKLORE_HOST",
            label="Grimmory URL",
            description="Base URL of your Grimmory instance",
            placeholder="http://booklore:6060",
            required=True,
            show_when={"field": "BOOKS_OUTPUT_MODE", "value": "booklore"},
        ),
        TextField(
            key="BOOKLORE_USERNAME",
            label="Username",
            description="Grimmory account username",
            required=True,
            show_when={"field": "BOOKS_OUTPUT_MODE", "value": "booklore"},
        ),
        PasswordField(
            key="BOOKLORE_PASSWORD",
            label="Password",
            description="Grimmory account password",
            required=True,
            show_when={"field": "BOOKS_OUTPUT_MODE", "value": "booklore"},
        ),
        SelectField(
            key="BOOKLORE_DESTINATION",
            label="Upload Destination",
            description="Choose whether uploads go directly to a specific library path or to Bookdrop for review.",
            options=[
                {
                    "value": "library",
                    "label": "Specific Library",
                    "description": "Upload directly into the selected library path.",
                },
                {
                    "value": "bookdrop",
                    "label": "Bookdrop",
                    "description": "Upload into Bookdrop and review metadata before importing to a library.",
                },
            ],
            default="library",
            show_when={"field": "BOOKS_OUTPUT_MODE", "value": "booklore"},
        ),
        SelectField(
            key="BOOKLORE_LIBRARY_ID",
            label="Library",
            description="Grimmory library to upload into.",
            options=get_booklore_library_options,
            required=True,
            user_overridable=True,
            show_when=[
                {"field": "BOOKS_OUTPUT_MODE", "value": "booklore"},
                {"field": "BOOKLORE_DESTINATION", "value": "library"},
            ],
        ),
        SelectField(
            key="BOOKLORE_PATH_ID",
            label="Path",
            description="Grimmory library path for uploads.",
            options=get_booklore_path_options,
            required=True,
            filter_by_field="BOOKLORE_LIBRARY_ID",
            user_overridable=True,
            show_when=[
                {"field": "BOOKS_OUTPUT_MODE", "value": "booklore"},
                {"field": "BOOKLORE_DESTINATION", "value": "library"},
            ],
        ),
        ActionButton(
            key="test_booklore",
            label="Test Connection",
            description="Verify your Grimmory configuration",
            style="primary",
            callback=check_booklore_connection,
            show_when={"field": "BOOKS_OUTPUT_MODE", "value": "booklore"},
        ),
        HeadingField(
            key="email_heading",
            title="Email",
            description="Send books as email attachments via SMTP. Audiobooks always use folder mode.",
            show_when={"field": "BOOKS_OUTPUT_MODE", "value": "email"},
        ),
        TextField(
            key="EMAIL_RECIPIENT",
            label="Default Email Recipient",
            description="Optional fallback email address when no per-user email recipient override is configured.",
            placeholder="reader@example.com",
            user_overridable=True,
            show_when={"field": "BOOKS_OUTPUT_MODE", "value": "email"},
        ),
        NumberField(
            key="EMAIL_ATTACHMENT_SIZE_LIMIT_MB",
            label="Attachment Size Limit (MB)",
            description="Maximum total attachment size per email. Email encoding adds overhead; keep this below your provider's limit.",
            default=25,
            min_value=1,
            max_value=600,
            show_when={"field": "BOOKS_OUTPUT_MODE", "value": "email"},
        ),
        TextField(
            key="EMAIL_SMTP_HOST",
            label="SMTP Host",
            description="SMTP server hostname or IP (e.g., smtp.gmail.com).",
            placeholder="smtp.example.com",
            required=True,
            show_when={"field": "BOOKS_OUTPUT_MODE", "value": "email"},
        ),
        NumberField(
            key="EMAIL_SMTP_PORT",
            label="SMTP Port",
            description="SMTP server port (587 is typical for STARTTLS, 465 for SSL).",
            default=587,
            min_value=1,
            max_value=65535,
            show_when={"field": "BOOKS_OUTPUT_MODE", "value": "email"},
        ),
        SelectField(
            key="EMAIL_SMTP_SECURITY",
            label="SMTP Security",
            description="Transport security mode for SMTP.",
            options=[
                {"value": "none", "label": "None", "description": "No TLS (not recommended)."},
                {
                    "value": "starttls",
                    "label": "STARTTLS",
                    "description": "Upgrade to TLS after connecting (recommended).",
                },
                {"value": "ssl", "label": "SSL/TLS", "description": "Connect using TLS (SMTPS)."},
            ],
            default="starttls",
            show_when={"field": "BOOKS_OUTPUT_MODE", "value": "email"},
        ),
        TextField(
            key="EMAIL_SMTP_USERNAME",
            label="Username",
            description="SMTP username (leave empty for no authentication).",
            placeholder="user@example.com",
            show_when={"field": "BOOKS_OUTPUT_MODE", "value": "email"},
        ),
        PasswordField(
            key="EMAIL_SMTP_PASSWORD",
            label="Password",
            description="SMTP password (required if Username is set).",
            show_when={"field": "BOOKS_OUTPUT_MODE", "value": "email"},
        ),
        TextField(
            key="EMAIL_FROM",
            label="From Address",
            description="From address used for the email. You can include a display name (e.g., Shelfmark <mail@example.com>). Leave blank to default to the SMTP username (when it is an email address).",
            placeholder="Shelfmark <mail@example.com>",
            show_when={"field": "BOOKS_OUTPUT_MODE", "value": "email"},
        ),
        TextField(
            key="EMAIL_SUBJECT_TEMPLATE",
            label="Subject Template",
            description="Email subject. Variables: {Author}, {Title}, {PrimaryTitle}, {Year}, {Series}, {SeriesPosition}, {Subtitle}, {Format}.",
            default="{Title}",
            placeholder="{Title}",
            show_when={"field": "BOOKS_OUTPUT_MODE", "value": "email"},
        ),
        NumberField(
            key="EMAIL_SMTP_TIMEOUT_SECONDS",
            label="SMTP Timeout (seconds)",
            description="How long to wait for SMTP operations before failing.",
            default=60,
            min_value=1,
            max_value=600,
            show_when={"field": "BOOKS_OUTPUT_MODE", "value": "email"},
        ),
        CheckboxField(
            key="EMAIL_ALLOW_UNVERIFIED_TLS",
            label="Allow Unverified TLS",
            description="Disable TLS certificate verification (not recommended).",
            default=False,
            show_when={"field": "BOOKS_OUTPUT_MODE", "value": "email"},
        ),
        ActionButton(
            key="test_email",
            label="Test SMTP Connection",
            description="Verify your SMTP configuration (connect + optional login).",
            style="primary",
            callback=check_email_connection,
            show_when={"field": "BOOKS_OUTPUT_MODE", "value": "email"},
        ),
        # === AUDIOBOOKS SECTION ===
        # Universal mode only
        HeadingField(
            key="audiobooks_heading",
            title="Audiobooks",
            description="Configure where audiobooks are saved.",
            universal_only=True,
        ),
        TextField(
            key="DESTINATION_AUDIOBOOK",
            label="Destination",
            description="Directory where downloaded audiobook files are saved. Leave empty to use the Books destination.",
            user_overridable=True,
            universal_only=True,
        ),
        ActionButton(
            key="test_destination_audiobook",
            label="Test Destination",
            description="Check that Shelfmark can create and write to this audiobook destination.",
            style="primary",
            callback=check_audiobook_destination,
            universal_only=True,
        ),
        SelectField(
            key="FILE_ORGANIZATION_AUDIOBOOK",
            label="File Organization",
            description="Choose how downloaded audiobook files are named and organized.",
            options=[
                {
                    "value": "none",
                    "label": "None",
                    "description": "Keep original filename from source",
                },
                {
                    "value": "rename",
                    "label": "Rename Only",
                    "description": "Rename single-file downloads; multi-file keeps original names.",
                },
                {
                    "value": "organize",
                    "label": "Rename and Organize",
                    "description": "Create folders and rename files using a template. Recommended for Audiobookshelf. Do not use with ingest folders.",
                },
            ],
            default="rename",
            universal_only=True,
        ),
        # Rename mode template - filename only
        _naming_template_field(
            key="TEMPLATE_AUDIOBOOK_RENAME",
            label="Naming Template",
            description=(
                "Variables: {Author}, {Title}, {Year}, {User}, {OriginalName} "
                "(source filename without extension), {Series}, {SeriesPosition}, {Subtitle}, "
                "{PrimaryTitle}, {PartNumber}. Use arbitrary prefix/suffix: "
                "{Vol. SeriesPosition - } outputs 'Vol. 2 - ' when set, nothing when empty. "
                "Rename templates are filename-only (no '/' or '\\'); use Organize for folders. "
                "Applies to single-file downloads."
            ),
            default="{Author} - {Title}",
            placeholder="{Author} - {Title}{ - Part }{PartNumber}",
            show_when={"field": "FILE_ORGANIZATION_AUDIOBOOK", "value": "rename"},
            universal_only=True,
        ),
        # Organize mode template - folders allowed
        _naming_template_field(
            key="TEMPLATE_AUDIOBOOK_ORGANIZE",
            label="Path Template",
            description=(
                "Use / to create folders. Variables: {Author}, {Title}, {Year}, {User}, "
                "{OriginalName} (source filename without extension), {Series}, {SeriesPosition}, "
                "{Subtitle}, {PrimaryTitle}, {PartNumber}. Use arbitrary prefix/suffix: "
                "{Vol. SeriesPosition - } outputs 'Vol. 2 - ' when set, nothing when empty."
            ),
            default="{Author}/{Title}/{Title}",
            placeholder="{Author}/{Series/}{Title}{ - Part }{PartNumber}",
            show_when={"field": "FILE_ORGANIZATION_AUDIOBOOK", "value": "organize"},
            universal_only=True,
        ),
        CheckboxField(
            key="HARDLINK_TORRENTS_AUDIOBOOK",
            label="Hardlink Audiobook Torrents",
            description="Create hardlinks instead of copying. Preserves seeding but archives won't be extracted. Don't use if destination is a library ingest folder.",
            default=True,
            universal_only=True,
        ),
        # === OPTIONS SECTION ===
        HeadingField(
            key="options_heading",
            title="Options",
        ),
        CheckboxField(
            key="AUTO_OPEN_DOWNLOADS_SIDEBAR",
            label="Auto-Open Downloads Sidebar",
            description="Automatically open the downloads sidebar when a new download is queued.",
            default=False,
        ),
        MultiSelectField(
            key="DOWNLOAD_TO_BROWSER_CONTENT_TYPES",
            label="Download to Browser",
            description="Automatically download completed files to your browser for the selected content types.",
            options=_DOWNLOAD_TO_BROWSER_CONTENT_TYPE_OPTIONS,
            default=[],
            variant="dropdown",
            user_overridable=True,
        ),
        NumberField(
            key="MAX_CONCURRENT_DOWNLOADS",
            label="Max Concurrent Downloads",
            description="Maximum number of simultaneous downloads.",
            default=3,
            min_value=1,
            max_value=10,
            requires_restart=True,
        ),
        NumberField(
            key="STATUS_TIMEOUT",
            label="Status Timeout (seconds)",
            description="How long to keep completed/failed downloads in the queue display.",
            default=3600,
            min_value=60,
            max_value=86400,
        ),
    ]


# Register the on_save handler for this tab
register_on_save("downloads", _on_save_downloads)
