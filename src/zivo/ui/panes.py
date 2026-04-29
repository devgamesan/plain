"""Compatibility re-export layer for pane widgets and helpers."""

from .child_pane import ChildPane
from .main_pane import MainPane
from .pane_rendering import (
    FILE_TYPE_COMPONENT_CLASSES,
    _ft_resolve_style,
    _guess_preview_lexer,
    _render_file_entries,
    _render_file_label,
    _resolve_component_styles,
    _style_without_background,
    build_entry_label,
    truncate_middle,
)
from .side_pane import SidePane

__all__ = [
    "ChildPane",
    "FILE_TYPE_COMPONENT_CLASSES",
    "MainPane",
    "SidePane",
    "_ft_resolve_style",
    "_guess_preview_lexer",
    "_render_file_entries",
    "_render_file_label",
    "_resolve_component_styles",
    "_style_without_background",
    "build_entry_label",
    "truncate_middle",
]
