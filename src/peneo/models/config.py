"""Configuration models for application startup defaults."""

from dataclasses import dataclass, field
from typing import Literal

ConfigSortField = Literal["name", "modified", "size"]
ConfigTheme = Literal["textual-dark", "textual-light"]
PasteConflictAction = Literal["overwrite", "skip", "rename", "prompt"]


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
class DisplayConfig:
    """Display-related startup defaults."""

    show_hidden_files: bool = False
    show_directory_sizes: bool = False
    theme: ConfigTheme = "textual-dark"
    default_sort_field: ConfigSortField = "name"
    default_sort_descending: bool = False
    directories_first: bool = True


@dataclass(frozen=True)
class BehaviorConfig:
    """Behavior-related startup defaults."""

    confirm_delete: bool = True
    paste_conflict_action: PasteConflictAction = "prompt"


@dataclass(frozen=True)
class LoggingConfig:
    """Log file output settings for startup/runtime failures."""

    enabled: bool = True
    path: str | None = None


@dataclass(frozen=True)
class BookmarkConfig:
    """Persisted bookmarked directory paths."""

    paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class HelpBarConfig:
    """Custom help bar text for each UI mode."""

    browsing: tuple[str, ...] = ()
    filter: tuple[str, ...] = ()
    rename: tuple[str, ...] = ()
    create: tuple[str, ...] = ()
    extract: tuple[str, ...] = ()
    zip: tuple[str, ...] = ()
    palette: tuple[str, ...] = ()
    palette_file_search: tuple[str, ...] = ()
    palette_grep_search: tuple[str, ...] = ()
    palette_history: tuple[str, ...] = ()
    palette_bookmarks: tuple[str, ...] = ()
    palette_go_to_path: tuple[str, ...] = ()
    shell: tuple[str, ...] = ()
    config: tuple[str, ...] = ()
    confirm_delete: tuple[str, ...] = ()
    detail: tuple[str, ...] = ()
    busy: tuple[str, ...] = ()
    split_terminal: tuple[str, ...] = ()


@dataclass(frozen=True)
class AppConfig:
    """Normalized application configuration."""

    terminal: TerminalConfig = field(default_factory=TerminalConfig)
    editor: EditorConfig = field(default_factory=EditorConfig)
    display: DisplayConfig = field(default_factory=DisplayConfig)
    behavior: BehaviorConfig = field(default_factory=BehaviorConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    bookmarks: BookmarkConfig = field(default_factory=BookmarkConfig)
    help_bar: HelpBarConfig = field(default_factory=HelpBarConfig)


@dataclass(frozen=True)
class ConfigLoadResult:
    """Result payload for loading a startup configuration file."""

    config: AppConfig = field(default_factory=AppConfig)
    path: str = ""
    warnings: tuple[str, ...] = ()
    created: bool = False
