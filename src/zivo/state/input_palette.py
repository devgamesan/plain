"""Command palette input dispatcher."""

import os

from zivo.windows_paths import is_search_workspace_path

from .actions import (
    BeginReplaceFromSearchResults,
    CancelCommandPalette,
    CycleFileSearchField,
    CycleFindReplaceField,
    CycleGrepReplaceField,
    CycleGrepReplaceSelectedField,
    CycleGrepSearchField,
    CycleReplaceField,
    MoveCommandPaletteCursor,
    OpenFindResultInEditor,
    OpenFindResultInGuiEditor,
    OpenGrepResultInEditor,
    OpenGrepResultInGuiEditor,
    SaveGrepResults,
    SetCommandPaletteQuery,
    SetFileSearchField,
    SetFileSearchTarget,
    SetFindReplaceField,
    SetGrepReplaceField,
    SetGrepReplaceSelectedField,
    SetGrepSearchField,
    SetGrepSearchScope,
    SetReplaceField,
    SetReplaceScope,
    SubmitCommandPalette,
)
from .command_palette import get_command_palette_items, normalize_command_palette_cursor
from .input_common import DispatchedActions, supported, warn
from .models import (
    AppState,
    CommandPaletteSource,
    FileSearchFieldId,
    FindReplaceFieldId,
    GrepReplaceFieldId,
    GrepReplaceSelectedFieldId,
    GrepSearchFieldId,
    ReplaceFieldId,
)
from .reducer_common import format_go_to_path_completion
from .selectors import compute_search_visible_window


def active_grep_field_value(state: AppState) -> str:
    if state.command_palette is None:
        return ""
    field = state.command_palette.grep_search.active_field
    if field == "scope":
        return ""
    if field == "keyword":
        return state.command_palette.grep_search.keyword or state.command_palette.query
    if field == "filename":
        return state.command_palette.grep_search.filename_filter
    if field == "include":
        return state.command_palette.grep_search.include_extensions
    return state.command_palette.grep_search.exclude_extensions


def active_file_search_field_value(state: AppState) -> str:
    if state.command_palette is None:
        return ""
    field = state.command_palette.file_search.active_field
    if field == "keyword":
        return state.command_palette.query
    if field == "include":
        return state.command_palette.file_search.include_extensions
    return state.command_palette.file_search.exclude_extensions


def active_replace_field_value(state: AppState) -> str:
    if state.command_palette is None:
        return ""
    field = state.command_palette.replace_preview.active_field
    if field == "scope":
        return ""
    if field == "find":
        return state.command_palette.replace_preview.find_text
    if field == "replace":
        return state.command_palette.replace_preview.replacement_text
    if field == "filename":
        return state.command_palette.replace_preview.filename_filter
    if field == "include":
        return state.command_palette.replace_preview.include_extensions
    return state.command_palette.replace_preview.exclude_extensions


def active_find_replace_field_value(state: AppState) -> str:
    field = state.command_palette.rff.active_field
    return (
        state.command_palette.rff.filename_query
        if field == "filename"
        else state.command_palette.rff.find_text
        if field == "find"
        else state.command_palette.rff.replacement_text
    )


def active_grep_replace_field_value(state: AppState) -> str:
    field = state.command_palette.grf.active_field
    return (
        state.command_palette.grf.keyword
        if field == "keyword"
        else state.command_palette.grf.replacement_text
        if field == "replace"
        else state.command_palette.grf.filename_filter
        if field == "filename"
        else state.command_palette.grf.include_extensions
        if field == "include"
        else state.command_palette.grf.exclude_extensions
    )


def active_grep_replace_selected_field_value(state: AppState) -> str:
    return (
        state.command_palette.grs.keyword
        if state.command_palette.grs.active_field == "keyword"
        else state.command_palette.grs.replacement_text
    )


def palette_extra_rows(palette_source: str | None) -> int:
    if palette_source == "grep_search":
        return 5
    if palette_source == "replace_text":
        return 2
    if palette_source == "file_search":
        return 3
    return 0


_SEARCH_PALETTE_SOURCES = frozenset(
    {
        "file_search",
        "grep_search",
        "go",
        "replace_text",
        "replace_in_found_files",
        "replace_in_grep_files",
        "grep_replace_selected",
    }
)


def _dispatch_go_input(
    state: AppState,
    *,
    key: str,
) -> DispatchedActions | None:
    if key != "tab" or state.command_palette is None:
        return None

    candidates = tuple(
        item.path for item in get_command_palette_items(state) if item.path is not None
    )
    if not candidates:
        if state.command_palette.go_completion.loading:
            return warn("Searching directories…")
        if state.command_palette.go_completion.error_message:
            return warn(state.command_palette.go_completion.error_message)
        return warn("No matching directory to complete")

    selected_path = candidates[
        normalize_command_palette_cursor(state, state.command_palette.cursor_index)
    ]
    completion_base_path = state.current_path
    if state.layout_mode == "transfer":
        transfer = (
            state.transfer_left if state.active_transfer_pane == "left" else state.transfer_right
        )
        if transfer is not None:
            completion_base_path = transfer.current_path
    completed_query = format_go_to_path_completion(
        selected_path,
        state.command_palette.query,
        completion_base_path,
        append_separator=len(candidates) == 1,
    )
    if len(candidates) == 1 and completed_query != os.sep:
        completed_query = completed_query.rstrip(os.sep) + os.sep
    return supported(SetCommandPaletteQuery(completed_query))


def _dispatch_file_search_input(
    state: AppState,
    *,
    key: str,
) -> DispatchedActions | None:
    palette = state.command_palette
    if palette is None:
        return None
    if key == "tab":
        return supported(CycleFileSearchField(delta=1))
    if key == "shift+tab":
        return supported(CycleFileSearchField(delta=-1))
    if key in ("left", "right"):
        if palette.file_search.active_field != "target":
            return warn("Use left/right arrows on the target field to change scope")
        delta = -1 if key == "left" else 1
        targets: tuple[str, ...] = ("files", "directories", "all")
        current = palette.file_search.target
        next_target = targets[(targets.index(current) + delta) % len(targets)]
        return supported(SetFileSearchTarget(target=next_target))
    if key == "ctrl+w":
        from .actions_palette import OpenSearchWorkspace

        return supported(OpenSearchWorkspace())
    if key == "backspace":
        if palette.file_search.active_field == "target":
            return warn("Use left/right arrows on the target field to change scope")
        active_field: FileSearchFieldId = palette.file_search.active_field
        next_value = active_file_search_field_value(state)[:-1]
        if active_field == "keyword":
            return supported(SetCommandPaletteQuery(next_value))
        return supported(SetFileSearchField(field=active_field, value=next_value))
    return None


def _dispatch_grep_search_input(
    state: AppState,
    *,
    key: str,
) -> DispatchedActions | None:
    palette = state.command_palette
    if palette is None:
        return None
    if key == "tab":
        return supported(CycleGrepSearchField(delta=1))
    if key == "shift+tab":
        return supported(CycleGrepSearchField(delta=-1))
    if key in ("left", "right"):
        return _dispatch_grep_scope_input(state, key=key)
    if key == "backspace":
        if palette.grep_search.active_field == "scope":
            return warn("Use left/right arrows to change scope")
        return supported(
            SetGrepSearchField(
                field=palette.grep_search.active_field,
                value=active_grep_field_value(state)[:-1],
            )
        )
    return None


def _dispatch_grep_scope_input(state: AppState, *, key: str) -> DispatchedActions:
    palette = state.command_palette
    if palette is None or palette.grep_search.active_field != "scope":
        return warn("Use left/right arrows on the scope field to change scope")
    scopes = ("current_directory",)
    if state.current_pane.selected_paths:
        scopes += ("selected_entries",)
    if is_search_workspace_path(state.current_path):
        scopes = ("search_workspace",)
        if state.current_pane.selected_paths:
            scopes += ("selected_entries",)
    delta = -1 if key == "left" else 1
    current = palette.grep_search.scope
    next_scope = scopes[(scopes.index(current) + delta) % len(scopes)]
    return supported(SetGrepSearchScope(scope=next_scope))


def _dispatch_replace_input(
    state: AppState,
    *,
    key: str,
) -> DispatchedActions | None:
    palette = state.command_palette
    if palette is None:
        return None
    if key == "tab":
        return supported(CycleReplaceField(delta=1))
    if key == "shift+tab":
        return supported(CycleReplaceField(delta=-1))
    if key in ("left", "right"):
        if palette.replace_preview.active_field != "scope":
            return warn("Use left/right arrows on the scope field to change scope")
        if palette.replace_preview.scope == "search_results":
            return warn("Search results scope is fixed to the displayed search results")
        scopes = ("current_file", "selected_files", "current_directory")
        current = palette.replace_preview.scope
        delta = -1 if key == "left" else 1
        next_scope = scopes[(scopes.index(current) + delta) % len(scopes)]
        return supported(SetReplaceScope(scope=next_scope))
    if key == "backspace":
        if palette.replace_preview.active_field == "scope":
            return warn("Use left/right arrows to change scope")
        return supported(
            SetReplaceField(
                field=palette.replace_preview.active_field,
                value=active_replace_field_value(state)[:-1],
            )
        )
    return None


def _dispatch_find_replace_input(
    state: AppState,
    *,
    key: str,
) -> DispatchedActions | None:
    palette = state.command_palette
    if palette is None:
        return None
    if key == "tab":
        return supported(CycleFindReplaceField(delta=1))
    if key == "shift+tab":
        return supported(CycleFindReplaceField(delta=-1))
    if key == "backspace":
        return supported(
            SetFindReplaceField(
                field=palette.rff.active_field,
                value=active_find_replace_field_value(state)[:-1],
            )
        )
    return None


def _dispatch_grep_replace_input(
    state: AppState,
    *,
    key: str,
) -> DispatchedActions | None:
    palette = state.command_palette
    if palette is None:
        return None
    if key == "tab":
        return supported(CycleGrepReplaceField(delta=1))
    if key == "shift+tab":
        return supported(CycleGrepReplaceField(delta=-1))
    if key == "backspace":
        return supported(
            SetGrepReplaceField(
                field=palette.grf.active_field,
                value=active_grep_replace_field_value(state)[:-1],
            )
        )
    return None


def _dispatch_grep_replace_selected_input(
    state: AppState,
    *,
    key: str,
) -> DispatchedActions | None:
    palette = state.command_palette
    if palette is None:
        return None
    if key == "tab":
        return supported(CycleGrepReplaceSelectedField(delta=1))
    if key == "shift+tab":
        return supported(CycleGrepReplaceSelectedField(delta=-1))
    if key == "backspace":
        return supported(
            SetGrepReplaceSelectedField(
                field=palette.grs.active_field,
                value=active_grep_replace_selected_field_value(state)[:-1],
            )
        )
    return None


def _dispatch_source_input(
    state: AppState,
    *,
    source: CommandPaletteSource | None,
    key: str,
) -> DispatchedActions | None:
    if source == "go":
        return _dispatch_go_input(state, key=key)
    if source == "file_search":
        return _dispatch_file_search_input(state, key=key)
    if source == "grep_search":
        return _dispatch_grep_search_input(state, key=key)
    if source == "replace_text":
        return _dispatch_replace_input(state, key=key)
    if source == "replace_in_found_files":
        return _dispatch_find_replace_input(state, key=key)
    if source == "replace_in_grep_files":
        return _dispatch_grep_replace_input(state, key=key)
    if source == "grep_replace_selected":
        return _dispatch_grep_replace_selected_input(state, key=key)
    return None


def _dispatch_cursor_input(
    state: AppState,
    *,
    source: CommandPaletteSource | None,
    key: str,
) -> DispatchedActions | None:
    if key == "escape":
        return supported(CancelCommandPalette())
    if key == "up" or (key == "k" and source not in _SEARCH_PALETTE_SOURCES):
        return supported(MoveCommandPaletteCursor(delta=-1))
    if key == "down" or (key == "j" and source not in _SEARCH_PALETTE_SOURCES):
        return supported(MoveCommandPaletteCursor(delta=1))
    if key == "ctrl+j":
        return supported(MoveCommandPaletteCursor(delta=1))
    if key == "ctrl+k":
        return supported(MoveCommandPaletteCursor(delta=-1))
    if key in {"pageup", "pagedown"}:
        visible = compute_search_visible_window(
            state.terminal_height,
            extra_rows=palette_extra_rows(source),
        )
        delta = -visible if key == "pageup" else visible
        return supported(MoveCommandPaletteCursor(delta=delta))
    if key == "home":
        return supported(MoveCommandPaletteCursor(delta=-999999))
    if key == "end":
        return supported(MoveCommandPaletteCursor(delta=999999))
    return None


def _dispatch_palette_action_input(
    state: AppState,
    *,
    source: CommandPaletteSource | None,
    key: str,
) -> DispatchedActions | None:
    if key == "enter":
        return supported(SubmitCommandPalette())
    if key == "ctrl+r" and source in {"file_search", "grep_search"}:
        return supported(BeginReplaceFromSearchResults())
    if key == "ctrl+e" and source == "grep_search":
        return supported(OpenGrepResultInEditor())
    if key == "ctrl+e" and source == "file_search":
        return supported(OpenFindResultInEditor())
    if key == "ctrl+o" and source == "grep_search":
        return supported(OpenGrepResultInGuiEditor())
    if key == "ctrl+o" and source == "file_search":
        return supported(OpenFindResultInGuiEditor())
    if key == "ctrl+x" and state.command_palette is not None:
        if source in {"grep_search", "replace_in_grep_files", "grep_replace_selected"}:
            return supported(SaveGrepResults())
        return warn("No grep results to save")
    if key == "backspace":
        current_query = state.command_palette.query if state.command_palette is not None else ""
        return supported(SetCommandPaletteQuery(current_query[:-1]))
    return None


def _dispatch_common_input(
    state: AppState,
    *,
    source: CommandPaletteSource | None,
    key: str,
) -> DispatchedActions | None:
    result = _dispatch_cursor_input(state, source=source, key=key)
    if result is not None:
        return result
    return _dispatch_palette_action_input(state, source=source, key=key)


def _dispatch_file_search_text(
    state: AppState,
    *,
    character: str,
) -> DispatchedActions:
    palette = state.command_palette
    if palette is None or palette.file_search.active_field == "target":
        return warn("Use left/right arrows on the target field to change scope")
    active_field: FileSearchFieldId = palette.file_search.active_field
    if active_field == "keyword":
        return supported(SetCommandPaletteQuery(f"{palette.query}{character}"))
    return supported(
        SetFileSearchField(
            field=active_field,
            value=f"{active_file_search_field_value(state)}{character}",
        )
    )


def _dispatch_grep_search_text(state: AppState, *, character: str) -> DispatchedActions:
    palette = state.command_palette
    if palette is None:
        return warn("Use left/right arrows to change scope")
    active_field: GrepSearchFieldId = palette.grep_search.active_field
    if active_field == "scope":
        return warn("Use left/right arrows to change scope")
    return supported(
        SetGrepSearchField(
            field=active_field,
            value=f"{active_grep_field_value(state)}{character}",
        )
    )


def _dispatch_replace_text(state: AppState, *, character: str) -> DispatchedActions:
    palette = state.command_palette
    if palette is None:
        return warn("Use left/right arrows to change scope")
    active_field: ReplaceFieldId = palette.replace_preview.active_field
    if active_field == "scope":
        return warn("Use left/right arrows to change scope")
    return supported(
        SetReplaceField(
            field=active_field,
            value=f"{active_replace_field_value(state)}{character}",
        )
    )


def _dispatch_find_replace_text(state: AppState, *, character: str) -> DispatchedActions:
    active: FindReplaceFieldId = state.command_palette.rff.active_field
    return supported(
        SetFindReplaceField(
            field=active,
            value=f"{active_find_replace_field_value(state)}{character}",
        )
    )


def _dispatch_grep_replace_text(state: AppState, *, character: str) -> DispatchedActions:
    active: GrepReplaceFieldId = state.command_palette.grf.active_field
    return supported(
        SetGrepReplaceField(
            field=active,
            value=f"{active_grep_replace_field_value(state)}{character}",
        )
    )


def _dispatch_grep_replace_selected_text(
    state: AppState,
    *,
    character: str,
) -> DispatchedActions:
    active: GrepReplaceSelectedFieldId = state.command_palette.grs.active_field
    return supported(
        SetGrepReplaceSelectedField(
            field=active,
            value=f"{active_grep_replace_selected_field_value(state)}{character}",
        )
    )


def _dispatch_text_input(
    state: AppState,
    *,
    source: CommandPaletteSource | None,
    character: str | None,
) -> DispatchedActions | None:
    palette = state.command_palette
    if not character or not character.isprintable():
        return None
    if palette is None:
        return supported(SetCommandPaletteQuery(character))
    if source == "file_search":
        return _dispatch_file_search_text(state, character=character)
    if source == "grep_search":
        return _dispatch_grep_search_text(state, character=character)
    if source == "replace_text":
        return _dispatch_replace_text(state, character=character)
    if source == "replace_in_found_files":
        return _dispatch_find_replace_text(state, character=character)
    if source == "replace_in_grep_files":
        return _dispatch_grep_replace_text(state, character=character)
    if source == "grep_replace_selected":
        return _dispatch_grep_replace_selected_text(state, character=character)
    return supported(SetCommandPaletteQuery(f"{palette.query}{character}"))


def _dispatch_palette_warning(source: CommandPaletteSource | None) -> DispatchedActions:
    if source in _SEARCH_PALETTE_SOURCES:
        if source == "grep_search":
            return warn(
                "Use Tab/Shift+Tab, type, arrows, Enter, "
                "Ctrl+r replace, Ctrl+e editor, Ctrl+x save results, or Esc"
            )
        return warn(
            "Use arrows, type to search, Enter, "
            "Ctrl+r replace, Ctrl+e editor, Ctrl+x save results, or Esc"
        )
    if source == "replace_text":
        return warn("Use Tab/Shift+Tab, type, arrows or Ctrl+j/k, Enter to apply, or Esc")
    return warn("Use arrows, type to filter, Enter to run, or Esc to cancel")


def dispatch_command_palette_input(
    state: AppState,
    *,
    key: str,
    character: str | None,
) -> DispatchedActions:
    source = state.command_palette.source if state.command_palette is not None else None
    result = _dispatch_source_input(state, source=source, key=key)
    if result is not None:
        return result
    result = _dispatch_common_input(state, source=source, key=key)
    if result is not None:
        return result
    result = _dispatch_text_input(state, source=source, character=character)
    if result is not None:
        return result
    return _dispatch_palette_warning(source)
