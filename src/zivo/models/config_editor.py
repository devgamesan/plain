"""Shared metadata for the settings exposed by Config Editor."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ConfigEditorField:
    """Describe one setting exposed by the cycle-based Config Editor."""

    field_id: str
    label: str
    category: str
    managed_settings: tuple[tuple[str, str], ...]


CONFIG_EDITOR_FIELDS: tuple[ConfigEditorField, ...] = (
    ConfigEditorField("editor.command", "Editor command", "Editors", (("editor", "command"),)),
    ConfigEditorField(
        "gui_editor.preset",
        "GUI editor",
        "Editors",
        (("gui_editor", "command"), ("gui_editor", "fallback_command")),
    ),
    ConfigEditorField(
        "display.show_hidden_files",
        "Show hidden files",
        "Appearance",
        (("display", "show_hidden_files"),),
    ),
    ConfigEditorField("display.theme", "Theme", "Appearance", (("display", "theme"),)),
    ConfigEditorField(
        "display.preview_syntax_theme",
        "Preview syntax theme",
        "Appearance",
        (("display", "preview_syntax_theme"),),
    ),
    ConfigEditorField(
        "display.enable_text_preview",
        "Text preview",
        "Preview",
        (("display", "enable_text_preview"),),
    ),
    ConfigEditorField(
        "display.enable_image_preview",
        "Image preview",
        "Preview",
        (("display", "enable_image_preview"),),
    ),
    ConfigEditorField(
        "display.enable_pdf_preview",
        "PDF preview",
        "Preview",
        (("display", "enable_pdf_preview"),),
    ),
    ConfigEditorField(
        "display.enable_office_preview",
        "Office preview",
        "Preview",
        (("display", "enable_office_preview"),),
    ),
    ConfigEditorField(
        "display.default_sort_field",
        "Default sort field",
        "Sorting",
        (("display", "default_sort_field"),),
    ),
    ConfigEditorField(
        "display.default_sort_descending",
        "Default sort descending",
        "Sorting",
        (("display", "default_sort_descending"),),
    ),
    ConfigEditorField(
        "display.directories_first",
        "Directories first",
        "Sorting",
        (("display", "directories_first"),),
    ),
    ConfigEditorField(
        "behavior.confirm_delete",
        "Confirm delete",
        "Safety",
        (("behavior", "confirm_delete"),),
    ),
)
