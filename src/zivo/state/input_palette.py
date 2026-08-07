"""Command palette input dispatcher."""

import os

from zivo.windows_paths import is_search_workspace_path

from .actions import (
    BeginGrepExport,
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
    SetCommandPaletteQuery,
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
from .command_palette import normalize_command_palette_cursor
from .input_common import DispatchedActions, supported, warn
from .models import (
    AppState,
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
        return 1
    return 0


def dispatch_command_palette_input(
    state: AppState,
    *,
    key: str,
    character: str | None,
) -> DispatchedActions:
    palette_source = state.command_palette.source if state.command_palette is not None else None
    search_palette = palette_source in {"file_search", "grep_search"}

    if (
        key == "tab"
        and state.command_palette is not None
        and state.command_palette.source == "go_to_path"
    ):
        candidates = state.command_palette.history_and_navigation.go_to_path_candidates
        if not candidates:
            return warn("No matching directory to complete")

        selected_path = candidates[
            normalize_command_palette_cursor(state, state.command_palette.cursor_index)
        ]
        completed_query = format_go_to_path_completion(
            selected_path,
            state.command_palette.query,
            state.current_path,
            append_separator=len(candidates) == 1,
        )
        if len(candidates) == 1 and completed_query != os.sep:
            completed_query = completed_query.rstrip(os.sep) + os.sep
        return supported(SetCommandPaletteQuery(completed_query))

    if key == "escape":
        return supported(CancelCommandPalette())

    if key == "tab" and palette_source == "file_search":
        return supported(CycleFileSearchField(delta=1))

    if key == "shift+tab" and palette_source == "file_search":
        return supported(CycleFileSearchField(delta=-1))

    if key == "tab" and palette_source == "grep_search":
        return supported(CycleGrepSearchField(delta=1))

    if key == "shift+tab" and palette_source == "grep_search":
        return supported(CycleGrepSearchField(delta=-1))

    if key == "tab" and palette_source == "replace_text":
        return supported(CycleReplaceField(delta=1))

    if key == "shift+tab" and palette_source == "replace_text":
        return supported(CycleReplaceField(delta=-1))

    if key == "tab" and palette_source == "replace_in_found_files":
        return supported(CycleFindReplaceField(delta=1))
    if key == "shift+tab" and palette_source == "replace_in_found_files":
        return supported(CycleFindReplaceField(delta=-1))
    if key == "tab" and palette_source == "replace_in_grep_files":
        return supported(CycleGrepReplaceField(delta=1))
    if key == "shift+tab" and palette_source == "replace_in_grep_files":
        return supported(CycleGrepReplaceField(delta=-1))
    if key == "tab" and palette_source == "grep_replace_selected":
        return supported(CycleGrepReplaceSelectedField(delta=1))
    if key == "shift+tab" and palette_source == "grep_replace_selected":
        return supported(CycleGrepReplaceSelectedField(delta=-1))


    if key in ("left", "right") and palette_source == "file_search":
        if (
            state.command_palette is not None
            and state.command_palette.file_search.active_field == "target"
        ):
            delta = -1 if key == "left" else 1
            targets: tuple[str, ...] = ("files", "directories", "all")
            current = state.command_palette.file_search.target
            index = targets.index(current)
            next_target = targets[(index + delta) % len(targets)]
            return supported(SetFileSearchTarget(target=next_target))
        return warn("Use left/right arrows on the target field to change scope")

    if key in ("left", "right") and palette_source == "grep_search":
        if state.command_palette.grep_search.active_field != "scope":
            return warn("Use left/right arrows on the scope field to change scope")
        scopes = ("current_directory",)
        if state.current_pane.selected_paths:
            scopes += ("selected_entries",)
        if is_search_workspace_path(state.current_path):
            scopes = ("search_workspace",)
            if state.current_pane.selected_paths:
                scopes += ("selected_entries",)
        current = state.command_palette.grep_search.scope
        index = scopes.index(current)
        next_scope = scopes[(index + (-1 if key == "left" else 1)) % len(scopes)]
        return supported(SetGrepSearchScope(scope=next_scope))

    if key in ("left", "right") and palette_source == "replace_text":
        if state.command_palette.replace_preview.active_field != "scope":
            return warn("Use left/right arrows on the scope field to change scope")
        scopes = (
            "current_file",
            "selected_files",
            "current_directory",
            "found_files",
            "grep_result_files",
        )
        current = state.command_palette.replace_preview.scope
        next_scope = scopes[(scopes.index(current) + (-1 if key == "left" else 1)) % len(scopes)]
        return supported(SetReplaceScope(scope=next_scope))

    if key == "up" or (key == "k" and not search_palette):
        return supported(MoveCommandPaletteCursor(delta=-1))

    if key == "down" or (key == "j" and not search_palette):
        return supported(MoveCommandPaletteCursor(delta=1))

    if key == "ctrl+j":
        return supported(MoveCommandPaletteCursor(delta=1))

    if key == "ctrl+k":
        return supported(MoveCommandPaletteCursor(delta=-1))

    if key == "pageup":
        extra_rows = palette_extra_rows(palette_source)
        visible = compute_search_visible_window(state.terminal_height, extra_rows=extra_rows)
        return supported(MoveCommandPaletteCursor(delta=-visible))

    if key == "pagedown":
        extra_rows = palette_extra_rows(palette_source)
        visible = compute_search_visible_window(state.terminal_height, extra_rows=extra_rows)
        return supported(MoveCommandPaletteCursor(delta=visible))

    if key == "home":
        return supported(MoveCommandPaletteCursor(delta=-999999))

    if key == "end":
        return supported(MoveCommandPaletteCursor(delta=999999))

    if key == "ctrl+w" and palette_source == "file_search":
        from .actions_palette import OpenSearchWorkspace

        return supported(OpenSearchWorkspace())

    if key == "enter":
        return supported(SubmitCommandPalette())

    if key == "backspace":
        if palette_source == "file_search":
            if (
                state.command_palette is not None
                and state.command_palette.file_search.active_field == "target"
            ):
                return warn("Use left/right arrows on the target field to change scope")
            current_query = state.command_palette.query if state.command_palette is not None else ""
            return supported(SetCommandPaletteQuery(current_query[:-1]))
        if palette_source == "grep_search":
            if state.command_palette.grep_search.active_field == "scope":
                return warn("Use left/right arrows to change scope")
            return supported(
                SetGrepSearchField(
                    field=state.command_palette.grep_search.active_field,
                    value=active_grep_field_value(state)[:-1],
                )
            )
        if palette_source == "replace_text":
            if state.command_palette.replace_preview.active_field == "scope":
                return warn("Use left/right arrows to change scope")
            return supported(
                SetReplaceField(
                    field=state.command_palette.replace_preview.active_field,
                    value=active_replace_field_value(state)[:-1],
                )
            )
        if palette_source == "replace_in_found_files":
            return supported(
                SetFindReplaceField(
                    field=state.command_palette.rff.active_field,
                    value=active_find_replace_field_value(state)[:-1],
                )
            )
        if palette_source == "replace_in_grep_files":
            return supported(
                SetGrepReplaceField(
                    field=state.command_palette.grf.active_field,
                    value=active_grep_replace_field_value(state)[:-1],
                )
            )
        if palette_source == "grep_replace_selected":
            return supported(
                SetGrepReplaceSelectedField(
                    field=state.command_palette.grs.active_field,
                    value=active_grep_replace_selected_field_value(state)[:-1],
                )
            )
        current_query = state.command_palette.query if state.command_palette is not None else ""
        return supported(SetCommandPaletteQuery(current_query[:-1]))

    if key == "ctrl+e" and state.command_palette is not None:
        if state.command_palette.source == "grep_search":
            return supported(OpenGrepResultInEditor())
        if state.command_palette.source == "file_search":
            return supported(OpenFindResultInEditor())

    if key == "ctrl+o" and state.command_palette is not None:
        if state.command_palette.source == "grep_search":
            return supported(OpenGrepResultInGuiEditor())
        if state.command_palette.source == "file_search":
            return supported(OpenFindResultInGuiEditor())

    if key == "ctrl+x" and state.command_palette is not None:
        if state.command_palette.source in {
            "grep_search",
            "replace_in_grep_files",
            "grep_replace_selected",
        }:
            return supported(BeginGrepExport())
        return warn("No grep results to export")

    if character and character.isprintable():
        if palette_source == "file_search":
            if (
                state.command_palette is not None
                and state.command_palette.file_search.active_field == "target"
            ):
                return warn("Use left/right arrows on the target field to change scope")
        if palette_source == "grep_search":
            active_field: GrepSearchFieldId = state.command_palette.grep_search.active_field
            if active_field == "scope":
                return warn("Use left/right arrows to change scope")
            return supported(
                SetGrepSearchField(
                    field=active_field,
                    value=f"{active_grep_field_value(state)}{character}",
                )
            )
        if palette_source == "replace_text":
            active_field: ReplaceFieldId = state.command_palette.replace_preview.active_field
            if active_field == "scope":
                return warn("Use left/right arrows to change scope")
            return supported(
                SetReplaceField(
                    field=active_field,
                    value=f"{active_replace_field_value(state)}{character}",
                )
            )
        if palette_source == "replace_in_found_files":
            active: FindReplaceFieldId = state.command_palette.rff.active_field
            return supported(
                SetFindReplaceField(
                    field=active,
                    value=f"{active_find_replace_field_value(state)}{character}",
                )
            )
        if palette_source == "replace_in_grep_files":
            active: GrepReplaceFieldId = state.command_palette.grf.active_field
            return supported(
                SetGrepReplaceField(
                    field=active,
                    value=f"{active_grep_replace_field_value(state)}{character}",
                )
            )
        if palette_source == "grep_replace_selected":
            active: GrepReplaceSelectedFieldId = state.command_palette.grs.active_field
            return supported(
                SetGrepReplaceSelectedField(
                    field=active,
                    value=f"{active_grep_replace_selected_field_value(state)}{character}",
                )
            )
        current_query = state.command_palette.query if state.command_palette is not None else ""
        return supported(SetCommandPaletteQuery(f"{current_query}{character}"))

    if search_palette:
        if state.command_palette is not None and state.command_palette.source == "grep_search":
            return warn(
                "Use Tab/Shift+Tab, type, arrows, Enter, "
                "Ctrl+e editor, Ctrl+x export, or Esc"
            )
        return warn(
            "Use arrows, type to search, Enter, "
            "Ctrl+e editor, Ctrl+x export, or Esc"
        )

    if palette_source == "replace_text":
        return warn("Use Tab/Shift+Tab, type, arrows or Ctrl+j/k, Enter to apply, or Esc")

    return warn("Use arrows, type to filter, Enter to run, or Esc to cancel")
