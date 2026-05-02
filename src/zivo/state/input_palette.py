"""Command palette input dispatcher."""

import os

from .actions import (
    CancelCommandPalette,
    CycleFileSearchField,
    CycleFindReplaceField,
    CycleGrepReplaceField,
    CycleGrepReplaceSelectedField,
    CycleGrepSearchField,
    CycleReplaceField,
    CycleSelectedFilesGrepField,
    MoveCommandPaletteCursor,
    OpenFindResultInEditor,
    OpenFindResultInGuiEditor,
    OpenGrepResultInEditor,
    OpenGrepResultInGuiEditor,
    SelectedFilesGrepKeywordChanged,
    SetCommandPaletteQuery,
    SetFileSearchTarget,
    SetFindReplaceField,
    SetGrepReplaceField,
    SetGrepReplaceSelectedField,
    SetGrepSearchField,
    SetReplaceField,
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
    if field == "find":
        return state.command_palette.replace_preview.find_text
    return state.command_palette.replace_preview.replacement_text


def active_find_replace_field_value(state: AppState) -> str:
    if state.command_palette is None:
        return ""
    field = state.command_palette.rff.active_field
    if field == "filename":
        return state.command_palette.rff.filename_query
    if field == "find":
        return state.command_palette.rff.find_text
    return state.command_palette.rff.replacement_text


def active_grep_replace_field_value(state: AppState) -> str:
    if state.command_palette is None:
        return ""
    field = state.command_palette.grf_active_field
    if field == "keyword":
        return state.command_palette.grf_keyword or state.command_palette.query
    if field == "replace":
        return state.command_palette.grf_replacement_text
    if field == "filename":
        return state.command_palette.grf_filename_filter
    if field == "include":
        return state.command_palette.grf_include_extensions
    return state.command_palette.grf_exclude_extensions


def active_grep_replace_selected_field_value(state: AppState) -> str:
    if state.command_palette is None:
        return ""
    field = state.command_palette.grs_active_field
    if field == "keyword":
        return state.command_palette.grs_keyword or state.command_palette.query
    return state.command_palette.grs_replacement_text


def palette_extra_rows(palette_source: str | None) -> int:
    if palette_source == "replace_in_found_files":
        return 3
    if palette_source == "replace_in_grep_files":
        return 5
    if palette_source == "grep_replace_selected":
        return 2
    if palette_source == "selected_files_grep":
        return 1
    if palette_source in {"grep_search", "replace_text"}:
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
    search_palette = palette_source in {"file_search", "grep_search", "selected_files_grep"}

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

    if key == "tab" and palette_source == "selected_files_grep":
        return supported(CycleSelectedFilesGrepField(delta=1))

    if key == "shift+tab" and palette_source == "selected_files_grep":
        return supported(CycleSelectedFilesGrepField(delta=-1))

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

    if key == "up" or (key == "k" and not search_palette):
        return supported(MoveCommandPaletteCursor(delta=-1))

    if key == "down" or (key == "j" and not search_palette):
        return supported(MoveCommandPaletteCursor(delta=1))

    if key == "ctrl+n":
        return supported(MoveCommandPaletteCursor(delta=1))

    if key == "ctrl+p":
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
            return supported(
                SetGrepSearchField(
                    field=state.command_palette.grep_search.active_field,
                    value=active_grep_field_value(state)[:-1],
                )
            )
        if palette_source == "replace_text":
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
                    field=state.command_palette.grf_active_field,
                    value=active_grep_replace_field_value(state)[:-1],
                )
            )
        if palette_source == "grep_replace_selected":
            return supported(
                SetGrepReplaceSelectedField(
                    field=state.command_palette.grs_active_field,
                    value=active_grep_replace_selected_field_value(state)[:-1],
                )
            )
        if palette_source == "selected_files_grep":
            if state.command_palette is not None:
                current_value = state.command_palette.sfg.keyword
            else:
                current_value = ""
            return supported(
                SelectedFilesGrepKeywordChanged(keyword=current_value[:-1])
            )
        current_query = state.command_palette.query if state.command_palette is not None else ""
        return supported(SetCommandPaletteQuery(current_query[:-1]))

    if key == "ctrl+e" and state.command_palette is not None:
        if state.command_palette.source in {"grep_search", "selected_files_grep"}:
            return supported(OpenGrepResultInEditor())
        if state.command_palette.source == "file_search":
            return supported(OpenFindResultInEditor())

    if key == "ctrl+o" and state.command_palette is not None:
        if state.command_palette.source in {"grep_search", "selected_files_grep"}:
            return supported(OpenGrepResultInGuiEditor())
        if state.command_palette.source == "file_search":
            return supported(OpenFindResultInGuiEditor())

    if character and character.isprintable():
        if palette_source == "file_search":
            if (
                state.command_palette is not None
                and state.command_palette.file_search.active_field == "target"
            ):
                return warn("Use left/right arrows on the target field to change scope")
        if palette_source == "grep_search":
            active_field: GrepSearchFieldId = state.command_palette.grep_search.active_field
            return supported(
                SetGrepSearchField(
                    field=active_field,
                    value=f"{active_grep_field_value(state)}{character}",
                )
            )
        if palette_source == "replace_text":
            active_field: ReplaceFieldId = state.command_palette.replace_preview.active_field
            return supported(
                SetReplaceField(
                    field=active_field,
                    value=f"{active_replace_field_value(state)}{character}",
                )
            )
        if palette_source == "replace_in_found_files":
            active_field_rff: FindReplaceFieldId = state.command_palette.rff.active_field
            return supported(
                SetFindReplaceField(
                    field=active_field_rff,
                    value=f"{active_find_replace_field_value(state)}{character}",
                )
            )
        if palette_source == "replace_in_grep_files":
            active_field_grf: GrepReplaceFieldId = state.command_palette.grf_active_field
            return supported(
                SetGrepReplaceField(
                    field=active_field_grf,
                    value=f"{active_grep_replace_field_value(state)}{character}",
                )
            )
        if palette_source == "grep_replace_selected":
            active_field_grs: GrepReplaceSelectedFieldId = state.command_palette.grs_active_field
            return supported(
                SetGrepReplaceSelectedField(
                    field=active_field_grs,
                    value=f"{active_grep_replace_selected_field_value(state)}{character}",
                )
            )
        if palette_source == "selected_files_grep":
            if state.command_palette is not None:
                current_value = state.command_palette.sfg.keyword
            else:
                current_value = ""
            return supported(
                SelectedFilesGrepKeywordChanged(keyword=f"{current_value}{character}")
            )
        current_query = state.command_palette.query if state.command_palette is not None else ""
        return supported(SetCommandPaletteQuery(f"{current_query}{character}"))

    if search_palette:
        if state.command_palette is not None and state.command_palette.source == "grep_search":
            return warn("Use Tab/Shift+Tab, type, arrows, Enter, Ctrl+e, or Esc")
        if (
            state.command_palette is not None
            and state.command_palette.source == "selected_files_grep"
        ):
            return warn("Use arrows, type to search, Enter, Ctrl+e for editor, or Esc")
        return warn("Use arrows, type to search, Enter, Ctrl+e for editor, or Esc")

    if palette_source == "replace_text":
        return warn("Use Tab/Shift+Tab, type, arrows or Ctrl+n/p, Enter to apply, or Esc")

    if palette_source == "replace_in_found_files":
        return warn("Use Tab/Shift+Tab, type, arrows or Ctrl+n/p, Enter to apply, or Esc")

    if palette_source == "replace_in_grep_files":
        return warn("Use Tab/Shift+Tab, type, arrows or Ctrl+n/p, Enter to apply, or Esc")

    if palette_source == "grep_replace_selected":
        return warn("Use Tab/Shift+Tab, type, arrows or Ctrl+n/p, Enter to apply, or Esc")

    return warn("Use arrows, type to filter, Enter to run, or Esc to cancel")
