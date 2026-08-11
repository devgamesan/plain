"""Configuration models for application startup defaults."""

from dataclasses import dataclass, field
from typing import Literal

from zivo.theme_support import AUTO_PREVIEW_SYNTAX_THEME, DEFAULT_APP_THEME

ConfigSortField = Literal["name", "modified", "size"]
ConfigTheme = str
PreviewSyntaxTheme = str
PreviewMaxKiB = Literal[64, 128, 256, 512, 1024]
ConfigLogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
PasteConflictAction = Literal["overwrite", "skip", "rename", "prompt"]
ImagePreviewMode = Literal["auto", "kitty", "chafa"]
CustomActionWhen = Literal["always", "single_file", "selection"]
CustomActionMode = Literal["background", "terminal", "terminal_window"]


@dataclass(frozen=True)
class TerminalConfig:
    """Terminal launch command templates keyed by target platform."""

    linux: tuple[str, ...] = ()
    macos: tuple[str, ...] = ()
    windows: tuple[str, ...] = ()


@dataclass(frozen=True)
class EditorConfig:
    """Terminal editor launch command configured by the user."""

    command: str | None = None


@dataclass(frozen=True)
class GuiEditorConfig:
    """GUI editor launch command templates configured by the user."""

    command: str = "code --goto {path}:{line}:{column}"
    fallback_command: str = "code {path}"


@dataclass(frozen=True)
class DisplayConfig:
    """Display-related startup defaults."""

    show_hidden_files: bool = False
    show_directory_sizes: bool = True
    enable_text_preview: bool = True
    enable_image_preview: bool = True
    image_preview_mode: ImagePreviewMode = "auto"
    enable_pdf_preview: bool = True
    enable_office_preview: bool = True
    show_help_bar: bool = True
    theme: ConfigTheme = DEFAULT_APP_THEME
    preview_syntax_theme: PreviewSyntaxTheme = AUTO_PREVIEW_SYNTAX_THEME
    preview_max_kib: PreviewMaxKiB = 64
    default_sort_field: ConfigSortField = "name"
    default_sort_descending: bool = False
    directories_first: bool = True
    grep_preview_context_lines: int = 3
    preview_word_wrap: bool = False


@dataclass(frozen=True)
class BehaviorConfig:
    """Behavior-related startup defaults."""

    confirm_delete: bool = True
    confirm_exit: bool = True
    paste_conflict_action: PasteConflictAction = "prompt"


@dataclass(frozen=True)
class LoggingConfig:
    """Log file output settings for startup/runtime failures."""

    enabled: bool = True
    path: str | None = None
    level: ConfigLogLevel = "ERROR"


@dataclass(frozen=True)
class BookmarkConfig:
    """Persisted bookmarked directory paths."""

    paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class FileSearchConfig:
    """File search behavior settings."""

    max_results: int | None = None


@dataclass(frozen=True)
class GrepSearchConfig:
    """Grep search behavior settings."""

    max_results: int | None = None


@dataclass(frozen=True)
class CustomActionConfig:
    """User-defined command palette action."""

    name: str
    command: tuple[str, ...]
    when: CustomActionWhen = "always"
    mode: CustomActionMode = "background"
    cwd: str | None = None
    extensions: tuple[str, ...] = ()


@dataclass(frozen=True)
class ActionsConfig:
    """User-defined command palette actions."""

    custom: tuple[CustomActionConfig, ...] = ()


@dataclass(frozen=True)
class AppConfig:
    """Normalized application configuration."""

    terminal: TerminalConfig = field(default_factory=TerminalConfig)
    editor: EditorConfig = field(default_factory=EditorConfig)
    gui_editor: GuiEditorConfig = field(default_factory=GuiEditorConfig)
    display: DisplayConfig = field(default_factory=DisplayConfig)
    behavior: BehaviorConfig = field(default_factory=BehaviorConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    bookmarks: BookmarkConfig = field(default_factory=BookmarkConfig)
    file_search: FileSearchConfig = field(default_factory=FileSearchConfig)
    grep_search: GrepSearchConfig = field(default_factory=GrepSearchConfig)
    actions: ActionsConfig = field(default_factory=ActionsConfig)


@dataclass(frozen=True)
class ConfigLoadResult:
    """Result payload for loading a startup configuration file."""

    config: AppConfig = field(default_factory=AppConfig)
    path: str = ""
    warnings: tuple[str, ...] = ()
    created: bool = False
    fatal: bool = False
