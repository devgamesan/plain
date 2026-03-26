"""Command palette definitions and filtering helpers."""

from dataclasses import dataclass

from .models import AppState, DirectoryEntryState


@dataclass(frozen=True)
class CommandPaletteItem:
    """Runtime command entry exposed to reducer and selectors."""

    id: str
    label: str
    shortcut: str | None
    enabled: bool


def get_filtered_command_palette_items(state: AppState) -> tuple[CommandPaletteItem, ...]:
    """Return visible command palette items filtered by the active query."""

    query = ""
    if state.command_palette is not None:
        query = state.command_palette.query

    return tuple(
        item for item in _build_command_palette_items(state) if _matches_query(item, query)
    )


def normalize_command_palette_cursor(state: AppState, cursor_index: int) -> int:
    """Clamp the palette cursor to the current filtered item list."""

    items = get_filtered_command_palette_items(state)
    if not items:
        return 0
    return max(0, min(len(items) - 1, cursor_index))


def _build_command_palette_items(state: AppState) -> tuple[CommandPaletteItem, ...]:
    target_paths = _select_target_paths(state)
    single_target_entry = _single_target_entry(state, target_paths)
    has_target = bool(target_paths)
    has_single_target = single_target_entry is not None

    items = [
        CommandPaletteItem(
            id="create_file",
            label="Create file",
            shortcut=None,
            enabled=True,
        ),
        CommandPaletteItem(
            id="create_dir",
            label="Create directory",
            shortcut=None,
            enabled=True,
        ),
    ]

    if has_target:
        items.append(
            CommandPaletteItem(
                id="copy_path",
                label="Copy path",
                shortcut=None,
                enabled=True,
            )
        )

    items.append(
        CommandPaletteItem(
            id="toggle_hidden",
            label=_hidden_files_label(state),
            shortcut=None,
            enabled=True,
        )
    )
    if has_single_target:
        items.append(
            CommandPaletteItem(
                id="run_shell",
                label="Run shell command",
                shortcut=None,
                enabled=False,
            )
        )

    items.append(
        CommandPaletteItem(
            id="open_terminal",
            label="Open terminal here",
            shortcut=None,
            enabled=True,
        )
    )

    return tuple(items)


def _matches_query(item: CommandPaletteItem, query: str) -> bool:
    if not query:
        return True
    lowered_query = query.casefold()
    return lowered_query in item.label.casefold()


def _hidden_files_label(state: AppState) -> str:
    return "Hide hidden files" if state.show_hidden else "Show hidden files"


def _select_target_paths(state: AppState) -> tuple[str, ...]:
    selected_paths = tuple(
        entry.path
        for entry in _active_current_entries(state)
        if entry.path in state.current_pane.selected_paths
    )
    if selected_paths:
        return selected_paths

    cursor_entry = _current_entry(state)
    if cursor_entry is None:
        return ()
    return (cursor_entry.path,)


def _single_target_entry(
    state: AppState,
    target_paths: tuple[str, ...],
) -> DirectoryEntryState | None:
    if len(target_paths) != 1:
        return None
    return _entry_for_path(state, target_paths[0])


def _current_entry(state: AppState) -> DirectoryEntryState | None:
    return _entry_for_path(state, state.current_pane.cursor_path)


def _entry_for_path(state: AppState, path: str | None) -> DirectoryEntryState | None:
    if path is None:
        return None
    for entry in _active_current_entries(state):
        if entry.path == path:
            return entry
    return None


def _active_current_entries(state: AppState) -> tuple[DirectoryEntryState, ...]:
    return state.current_pane.entries
