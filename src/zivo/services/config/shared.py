"""Shared config metadata used by load and render flows."""

from __future__ import annotations

from zivo.theme_support import SUPPORTED_APP_THEMES, SUPPORTED_PREVIEW_SYNTAX_THEMES

VALID_SORT_FIELDS = frozenset({"name", "modified", "size"})
VALID_THEMES = frozenset(SUPPORTED_APP_THEMES)
VALID_PREVIEW_SYNTAX_THEMES = frozenset(SUPPORTED_PREVIEW_SYNTAX_THEMES)
VALID_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})
VALID_PASTE_ACTIONS = frozenset({"overwrite", "skip", "rename", "prompt"})
VALID_SPLIT_TERMINAL_POSITIONS = frozenset({"bottom", "right", "overlay"})
VALID_TERMINAL_LAUNCH_MODES = frozenset({"window", "foreground"})
VALID_PREVIEW_MAX_KIB = frozenset({64, 128, 256, 512, 1024})
VALID_TERMINAL_EDITOR_NAMES = frozenset(
    {"emacs", "helix", "hx", "kak", "micro", "nano", "nvim", "vi", "vim"}
)
VALIDATION_PATH = "/tmp/zivo"

HELP_BAR_FIELDS = (
    "browsing",
    "transfer",
    "filter",
    "rename",
    "create",
    "extract",
    "zip",
    "palette",
    "palette_file_search",
    "palette_grep_search",
    "palette_history",
    "palette_bookmarks",
    "palette_go_to_path",
    "shell",
    "config",
    "confirm_delete",
    "detail",
    "busy",
    "split_terminal",
)
