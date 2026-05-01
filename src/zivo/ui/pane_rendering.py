"""Shared rendering helpers for pane widgets."""

from collections.abc import Sequence
from functools import lru_cache

from rich.cells import cell_len
from rich.style import Style
from rich.syntax import Syntax
from rich.text import Text

from zivo.models.shell_data import PaneEntry

ELLIPSIS = "~"
FILE_TYPE_COMPONENT_CLASSES = frozenset(
    {
        "ft-cut",
        "ft-directory",
        "ft-directory-cut",
        "ft-directory-sel",
        "ft-directory-sel-table",
        "ft-executable",
        "ft-executable-cut",
        "ft-executable-sel",
        "ft-selected",
        "ft-selected-cut",
        "ft-symlink",
        "ft-symlink-cut",
        "ft-symlink-sel",
    }
)


@lru_cache(maxsize=256)
def _guess_preview_lexer(path: str) -> str:
    try:
        return Syntax.guess_lexer(path)
    except Exception:
        return "text"


def build_entry_label(entry: PaneEntry) -> str:
    """Return the complete entry label before width-based truncation."""

    if entry.name_detail is None:
        return entry.name
    return f"{entry.name}  ({entry.name_detail})"


def truncate_middle(text: str, max_width: int) -> str:
    """Shorten text with a middle marker while preserving a useful suffix."""

    if max_width <= 0:
        return ""
    if cell_len(text) <= max_width:
        return text
    if max_width == 1:
        return ELLIPSIS
    if max_width == 2:
        return f"{ELLIPSIS}{_take_suffix_cells(text, 1)}"

    remaining_width = max_width - cell_len(ELLIPSIS)
    preferred_suffix = _preferred_suffix(text)
    if preferred_suffix and cell_len(preferred_suffix) <= remaining_width - 1:
        suffix_width = cell_len(preferred_suffix)
    else:
        suffix_width = max(1, remaining_width // 2)
    prefix_width = remaining_width - suffix_width
    if prefix_width <= 0:
        prefix_width = 1
        suffix_width = remaining_width - prefix_width

    prefix = _take_prefix_cells(text, prefix_width)
    suffix = _take_suffix_cells(text, suffix_width)
    return f"{prefix}{ELLIPSIS}{suffix}"


def _preferred_suffix(text: str) -> str:
    dot_index = text.rfind(".")
    if dot_index <= 0 or dot_index == len(text) - 1:
        return ""
    return text[dot_index:]


def _take_prefix_cells(text: str, width: int) -> str:
    if width <= 0:
        return ""
    collected: list[str] = []
    used_width = 0
    for character in text:
        character_width = cell_len(character)
        if used_width + character_width > width:
            break
        collected.append(character)
        used_width += character_width
    return "".join(collected)


def _take_suffix_cells(text: str, width: int) -> str:
    if width <= 0:
        return ""
    collected: list[str] = []
    used_width = 0
    for character in reversed(text):
        character_width = cell_len(character)
        if used_width + character_width > width:
            break
        collected.append(character)
        used_width += character_width
    return "".join(reversed(collected))


def _resolve_component_styles(widget: object) -> dict[str, Style]:
    """Resolve all file-type component styles from the widget's CSS."""

    return {
        name: widget.get_component_rich_style(name)  # type: ignore[union-attr]
        for name in FILE_TYPE_COMPONENT_CLASSES
    }


def _style_without_background(style: Style | None) -> Style | None:
    """Drop background color so table cell text doesn't paint its own block."""

    if style is None or style.bgcolor is None:
        return style
    return Style(
        color=style.color,
        bold=style.bold,
        dim=style.dim,
        italic=style.italic,
        underline=style.underline,
        blink=style.blink,
        blink2=style.blink2,
        reverse=style.reverse,
        conceal=style.conceal,
        strike=style.strike,
        underline2=style.underline2,
        frame=style.frame,
        encircle=style.encircle,
        overline=style.overline,
        link=style.link,
        meta=style.meta,
    )


def _ft_style_name(
    entry: PaneEntry,
    *,
    selected_directory_style: str,
    selected_cut_style: str,
) -> str | None:
    """Return the component class name that should style the entry."""

    if entry.cut:
        if entry.symlink:
            return "ft-symlink-cut"
        if entry.kind == "dir":
            return "ft-directory-cut"
        if entry.executable:
            return "ft-executable-cut"
        if entry.selected:
            return selected_cut_style
        return "ft-cut"
    if entry.symlink:
        if entry.selected:
            return "ft-symlink-sel"
        return "ft-symlink"
    if entry.kind == "dir":
        if entry.selected:
            return selected_directory_style
        return "ft-directory"
    if entry.executable:
        if entry.selected:
            return "ft-executable-sel"
        return "ft-executable"
    if entry.selected:
        return "ft-selected"
    return None


def _ft_resolve_style(
    entry: PaneEntry,
    styles: dict[str, Style],
    *,
    selected_directory_style: str,
    selected_cut_style: str,
) -> Style | None:
    """Resolve the file-type Rich style for an entry."""

    style_name = _ft_style_name(
        entry,
        selected_directory_style=selected_directory_style,
        selected_cut_style=selected_cut_style,
    )
    if style_name is None:
        return None
    return styles.get(style_name)


def _render_file_label(
    entry: PaneEntry,
    render_width: int,
    styles: dict[str, Style],
    *,
    selected_directory_style: str,
    selected_cut_style: str,
    hovered_path: str | None = None,
) -> Text:
    """Render a single file entry label with resolved theme styles."""

    label = build_entry_label(entry)
    if render_width > 0:
        label = truncate_middle(label, render_width)
    style = _ft_resolve_style(
        entry,
        styles,
        selected_directory_style=selected_directory_style,
        selected_cut_style=selected_cut_style,
    )
    style = _style_without_background(style)
    if hovered_path is not None and entry.path == hovered_path:
        style = (style or Style()) + Style(reverse=True)
    text = Text(label) if style is None else Text(label, style=style)
    if label:
        text.stylize(Style(meta={"entry_path": entry.path}), 0, len(label))
    return text


def _render_file_entries(
    entries: Sequence[PaneEntry],
    render_width: int,
    styles: dict[str, Style],
    *,
    selected_directory_style: str,
    selected_cut_style: str,
    hovered_path: str | None = None,
) -> Text:
    """Render a sequence of file entries as a single Rich Text block."""

    if not entries:
        return Text()
    return Text("\n").join(
        [
            _render_file_label(
                entry,
                render_width,
                styles,
                selected_directory_style=selected_directory_style,
                selected_cut_style=selected_cut_style,
                hovered_path=hovered_path,
            )
            for entry in entries
        ]
    )
