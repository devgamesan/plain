"""Command palette reducer handlers."""

from dataclasses import replace
from pathlib import Path

from peneo.models import ExternalLaunchRequest

from .actions import (
    Action,
    BeginCommandPalette,
    BeginCreateInput,
    BeginDeleteTargets,
    BeginFileSearch,
    BeginGoToPath,
    BeginGrepSearch,
    BeginHistorySearch,
    BeginRenameInput,
    CancelCommandPalette,
    DismissAttributeDialog,
    FileSearchCompleted,
    FileSearchFailed,
    GoBack,
    GoForward,
    GoToHomeDirectory,
    GrepSearchCompleted,
    GrepSearchFailed,
    MoveCommandPaletteCursor,
    OpenPathInEditor,
    OpenPathWithDefaultApp,
    OpenTerminalAtPath,
    ReloadDirectory,
    RequestBrowserSnapshot,
    SetCommandPaletteQuery,
    SubmitCommandPalette,
    ToggleHiddenFiles,
    ToggleSplitTerminal,
)
from .command_palette import get_command_palette_items, normalize_command_palette_cursor
from .effects import ReduceResult, RunFileSearchEffect, RunGrepSearchEffect
from .models import (
    AppState,
    AttributeInspectionState,
    CommandPaletteState,
    ConfigEditorState,
    NotificationState,
)
from .reducer_common import (
    ReducerFn,
    done,
    expand_and_validate_path,
    filter_file_search_results,
    is_regex_file_search_query,
    run_external_launch_request,
    single_target_entry,
    single_target_path,
)
from .selectors import select_target_paths


def handle_palette_action(
    state: AppState,
    action: Action,
    reduce_state: ReducerFn,
) -> ReduceResult | None:
    if isinstance(action, BeginCommandPalette):
        return done(
            replace(
                state,
                ui_mode="PALETTE",
                notification=None,
                pending_input=None,
                command_palette=CommandPaletteState(),
                pending_file_search_request_id=None,
                pending_grep_search_request_id=None,
                delete_confirmation=None,
                name_conflict=None,
                attribute_inspection=None,
            )
        )

    if isinstance(action, BeginFileSearch):
        return done(
            replace(
                state,
                ui_mode="PALETTE",
                notification=None,
                pending_input=None,
                command_palette=CommandPaletteState(source="file_search"),
                pending_file_search_request_id=None,
                pending_grep_search_request_id=None,
                delete_confirmation=None,
                name_conflict=None,
                attribute_inspection=None,
            )
        )

    if isinstance(action, BeginGrepSearch):
        return done(
            replace(
                state,
                ui_mode="PALETTE",
                notification=None,
                pending_input=None,
                command_palette=CommandPaletteState(source="grep_search"),
                pending_file_search_request_id=None,
                pending_grep_search_request_id=None,
                delete_confirmation=None,
                name_conflict=None,
                attribute_inspection=None,
            )
        )

    if isinstance(action, BeginHistorySearch):
        history_items = tuple(reversed(state.history.back)) + state.history.forward
        return done(
            replace(
                state,
                ui_mode="PALETTE",
                notification=None,
                pending_input=None,
                command_palette=CommandPaletteState(
                    source="history",
                    history_results=history_items,
                ),
                pending_file_search_request_id=None,
                pending_grep_search_request_id=None,
                delete_confirmation=None,
                name_conflict=None,
                attribute_inspection=None,
            )
        )

    if isinstance(action, BeginGoToPath):
        return done(
            replace(
                state,
                ui_mode="PALETTE",
                notification=None,
                pending_input=None,
                command_palette=CommandPaletteState(source="go_to_path"),
                pending_file_search_request_id=None,
                pending_grep_search_request_id=None,
                delete_confirmation=None,
                name_conflict=None,
                attribute_inspection=None,
            )
        )

    if isinstance(action, CancelCommandPalette):
        return done(
            replace(
                state,
                ui_mode="BROWSING",
                notification=None,
                command_palette=None,
                pending_file_search_request_id=None,
                pending_grep_search_request_id=None,
                name_conflict=None,
                attribute_inspection=None,
            )
        )

    if isinstance(action, DismissAttributeDialog):
        return done(
            replace(
                state,
                ui_mode="BROWSING",
                notification=None,
                attribute_inspection=None,
            )
        )

    if isinstance(action, MoveCommandPaletteCursor):
        if state.command_palette is None:
            return done(state)
        return done(
            replace(
                state,
                command_palette=replace(
                    state.command_palette,
                    cursor_index=normalize_command_palette_cursor(
                        state,
                        state.command_palette.cursor_index + action.delta,
                    ),
                ),
            )
        )

    if isinstance(action, SetCommandPaletteQuery):
        if state.command_palette is None:
            return done(state)
        next_palette = replace(
            state.command_palette,
            query=action.query,
            cursor_index=0,
            file_search_error_message=None,
            grep_search_error_message=None,
        )
        if state.command_palette.source == "grep_search":
            stripped_query = action.query.strip()
            if not stripped_query:
                return done(
                    replace(
                        state,
                        command_palette=replace(
                            next_palette,
                            grep_search_results=(),
                            grep_search_error_message=None,
                        ),
                        pending_grep_search_request_id=None,
                    )
                )
            request_id = state.next_request_id
            next_state = replace(
                state,
                command_palette=next_palette,
                pending_grep_search_request_id=request_id,
                next_request_id=request_id + 1,
            )
            return done(
                next_state,
                RunGrepSearchEffect(
                    request_id=request_id,
                    root_path=state.current_path,
                    query=stripped_query,
                    show_hidden=state.show_hidden,
                ),
            )

        if state.command_palette.source == "go_to_path":
            expanded_path = expand_and_validate_path(action.query, state.current_path)
            return done(
                replace(
                    state,
                    command_palette=replace(next_palette, go_to_path_preview=expanded_path),
                )
            )

        if state.command_palette.source != "file_search":
            return done(replace(state, command_palette=next_palette))

        stripped_query = action.query.strip()
        if not stripped_query:
            return done(
                replace(
                    state,
                    command_palette=replace(
                        next_palette,
                        file_search_results=(),
                        file_search_error_message=None,
                    ),
                    pending_file_search_request_id=None,
                    pending_grep_search_request_id=None,
                )
            )
        is_regex_query = is_regex_file_search_query(stripped_query)
        normalized_query = stripped_query.casefold()
        if (
            not is_regex_query
            and state.command_palette.file_search_cache_query
            and normalized_query.startswith(state.command_palette.file_search_cache_query)
            and state.command_palette.file_search_cache_root_path == state.current_path
            and state.command_palette.file_search_cache_show_hidden == state.show_hidden
        ):
            return done(
                replace(
                    state,
                    command_palette=replace(
                        next_palette,
                        file_search_results=filter_file_search_results(
                            state.command_palette.file_search_cache_results,
                            normalized_query,
                        ),
                    ),
                    pending_file_search_request_id=None,
                    pending_grep_search_request_id=None,
                )
            )
        request_id = state.next_request_id
        next_state = replace(
            state,
            command_palette=next_palette,
            pending_file_search_request_id=request_id,
            pending_grep_search_request_id=None,
            next_request_id=request_id + 1,
        )
        return done(
            next_state,
            RunFileSearchEffect(
                request_id=request_id,
                root_path=state.current_path,
                query=stripped_query,
                show_hidden=state.show_hidden,
            ),
        )

    if isinstance(action, SubmitCommandPalette):
        if state.command_palette is None:
            return done(state)
        if state.command_palette.source in {"file_search", "grep_search"}:
            if state.command_palette.source == "file_search":
                results = state.command_palette.file_search_results
                message = state.command_palette.file_search_error_message or "No matching files"
            else:
                results = state.command_palette.grep_search_results
                message = state.command_palette.grep_search_error_message or "No matching lines"
            if not results:
                return done(
                    replace(
                        state,
                        notification=NotificationState(
                            level="warning",
                            message=message,
                        ),
                    )
                )
            selected_result = results[
                normalize_command_palette_cursor(state, state.command_palette.cursor_index)
            ]
            next_state = replace(
                state,
                ui_mode="BROWSING",
                notification=None,
                command_palette=None,
                pending_file_search_request_id=None,
                pending_grep_search_request_id=None,
                attribute_inspection=None,
            )
            return reduce_state(
                next_state,
                RequestBrowserSnapshot(
                    str(Path(selected_result.path).parent),
                    cursor_path=selected_result.path,
                    blocking=True,
                ),
            )

        if state.command_palette.source == "history":
            items = get_command_palette_items(state)
            if not items:
                return done(
                    replace(
                        state,
                        notification=NotificationState(
                            level="warning",
                            message="No directory history",
                        ),
                    )
                )
            selected_item = items[
                normalize_command_palette_cursor(state, state.command_palette.cursor_index)
            ]
            next_state = replace(
                state,
                ui_mode="BROWSING",
                notification=None,
                command_palette=None,
                pending_file_search_request_id=None,
                pending_grep_search_request_id=None,
                attribute_inspection=None,
            )
            return reduce_state(
                next_state,
                RequestBrowserSnapshot(
                    selected_item.path,
                    blocking=True,
                ),
            )

        if state.command_palette.source == "go_to_path":
            expanded_path = expand_and_validate_path(
                state.command_palette.query,
                state.current_path,
            )
            if expanded_path is None:
                return done(
                    replace(
                        state,
                        notification=NotificationState(
                            level="error",
                            message="Path does not exist or is not a directory",
                        ),
                    )
                )
            next_state = replace(
                state,
                ui_mode="BROWSING",
                notification=None,
                command_palette=None,
                pending_file_search_request_id=None,
                pending_grep_search_request_id=None,
                attribute_inspection=None,
            )
            return reduce_state(
                next_state,
                RequestBrowserSnapshot(expanded_path, blocking=True),
            )

        items = get_command_palette_items(state)
        if not items:
            return done(
                replace(
                    state,
                    notification=NotificationState(level="warning", message="No matching command"),
                )
            )
        selected_item = items[
            normalize_command_palette_cursor(state, state.command_palette.cursor_index)
        ]
        if not selected_item.enabled:
            return done(
                replace(
                    state,
                    notification=NotificationState(
                        level="warning",
                        message=f"{selected_item.label} is not available yet",
                    ),
                )
            )
        next_state = replace(
            state,
            ui_mode="BROWSING",
            notification=None,
            command_palette=None,
            pending_file_search_request_id=None,
            pending_grep_search_request_id=None,
            attribute_inspection=None,
        )
        if selected_item.id == "file_search":
            return reduce_state(next_state, BeginFileSearch())
        if selected_item.id == "grep_search":
            return reduce_state(next_state, BeginGrepSearch())
        if selected_item.id == "history_search":
            return reduce_state(next_state, BeginHistorySearch())
        if selected_item.id == "go_back":
            return reduce_state(next_state, GoBack())
        if selected_item.id == "go_forward":
            return reduce_state(next_state, GoForward())
        if selected_item.id == "go_to_path":
            return reduce_state(next_state, BeginGoToPath())
        if selected_item.id == "go_to_home_directory":
            return reduce_state(next_state, GoToHomeDirectory())
        if selected_item.id == "reload_directory":
            return reduce_state(next_state, ReloadDirectory())
        if selected_item.id == "toggle_split_terminal":
            return reduce_state(next_state, ToggleSplitTerminal())
        if selected_item.id == "show_attributes":
            entry = single_target_entry(state)
            if entry is None:
                return done(
                    replace(
                        state,
                        notification=NotificationState(
                            level="warning",
                            message="Show attributes requires a single target",
                        ),
                    )
                )
            return done(
                replace(
                    state,
                    ui_mode="DETAIL",
                    notification=None,
                    command_palette=None,
                    pending_file_search_request_id=None,
                    pending_grep_search_request_id=None,
                    attribute_inspection=AttributeInspectionState(
                        name=entry.name,
                        kind=entry.kind,
                        path=entry.path,
                        size_bytes=entry.size_bytes,
                        modified_at=entry.modified_at,
                        hidden=entry.hidden,
                        permissions_mode=entry.permissions_mode,
                    ),
                )
            )
        if selected_item.id == "copy_path":
            target_paths = select_target_paths(state)
            if not target_paths:
                return done(
                    replace(
                        state,
                        notification=NotificationState(level="warning", message="Nothing to copy"),
                    )
                )
            return run_external_launch_request(
                next_state,
                ExternalLaunchRequest(kind="copy_paths", paths=target_paths),
            )
        if selected_item.id == "rename":
            target_path = single_target_path(state)
            if target_path is None:
                return done(
                    replace(
                        next_state,
                        notification=NotificationState(
                            level="warning",
                            message="Rename requires a single target",
                        ),
                    )
                )
            return reduce_state(next_state, BeginRenameInput(path=target_path))
        if selected_item.id == "open_in_editor":
            entry = single_target_entry(state)
            if entry is None:
                return done(
                    replace(
                        next_state,
                        notification=NotificationState(
                            level="warning",
                            message="Open in editor requires a single target",
                        ),
                    )
                )
            if entry.kind != "file":
                return done(
                    replace(
                        next_state,
                        notification=NotificationState(
                            level="warning",
                            message="Can only open files in editor",
                        ),
                    )
                )
            return reduce_state(next_state, OpenPathInEditor(path=entry.path))
        if selected_item.id == "delete_targets":
            target_paths = select_target_paths(state)
            if not target_paths:
                return done(
                    replace(
                        state,
                        notification=NotificationState(
                            level="warning",
                            message="Nothing to delete",
                        ),
                    )
                )
            return reduce_state(next_state, BeginDeleteTargets(paths=target_paths))
        if selected_item.id == "open_file_manager":
            return reduce_state(next_state, OpenPathWithDefaultApp(next_state.current_path))
        if selected_item.id == "open_terminal":
            return reduce_state(next_state, OpenTerminalAtPath(next_state.current_path))
        if selected_item.id == "toggle_hidden":
            return reduce_state(next_state, ToggleHiddenFiles())
        if selected_item.id == "edit_config":
            return done(
                replace(
                    state,
                    ui_mode="CONFIG",
                    notification=None,
                    command_palette=None,
                    pending_file_search_request_id=None,
                    pending_grep_search_request_id=None,
                    attribute_inspection=None,
                    config_editor=ConfigEditorState(
                        path=state.config_path,
                        draft=state.config,
                    )
                )
            )
        if selected_item.id == "create_file":
            return reduce_state(next_state, BeginCreateInput("file"))
        if selected_item.id == "create_dir":
            return reduce_state(next_state, BeginCreateInput("dir"))
        return done(next_state)

    if isinstance(action, FileSearchCompleted):
        if (
            action.request_id != state.pending_file_search_request_id
            or state.command_palette is None
            or state.command_palette.source != "file_search"
            or state.command_palette.query.strip() != action.query
        ):
            return done(state)
        cache_query = ""
        cache_results = ()
        if not is_regex_file_search_query(action.query):
            cache_query = action.query.casefold()
            cache_results = action.results
        return done(
            replace(
                state,
                command_palette=replace(
                    state.command_palette,
                    file_search_results=action.results,
                    file_search_error_message=None,
                    cursor_index=0,
                    file_search_cache_query=cache_query,
                    file_search_cache_results=cache_results,
                    file_search_cache_root_path=state.current_path,
                    file_search_cache_show_hidden=state.show_hidden,
                ),
                pending_file_search_request_id=None,
            )
        )

    if isinstance(action, FileSearchFailed):
        if action.request_id != state.pending_file_search_request_id:
            return done(state)
        if state.command_palette is not None and action.invalid_query:
            return done(
                replace(
                    state,
                    command_palette=replace(
                        state.command_palette,
                        file_search_results=(),
                        file_search_error_message=action.message,
                    ),
                    pending_file_search_request_id=None,
                )
            )
        return done(
            replace(
                state,
                notification=NotificationState(level="error", message=action.message),
                pending_file_search_request_id=None,
            )
        )

    if isinstance(action, GrepSearchCompleted):
        if (
            action.request_id != state.pending_grep_search_request_id
            or state.command_palette is None
            or state.command_palette.source != "grep_search"
            or state.command_palette.query.strip() != action.query
        ):
            return done(state)
        return done(
            replace(
                state,
                command_palette=replace(
                    state.command_palette,
                    grep_search_results=action.results,
                    grep_search_error_message=None,
                    cursor_index=0,
                ),
                pending_grep_search_request_id=None,
            )
        )

    if isinstance(action, GrepSearchFailed):
        if action.request_id != state.pending_grep_search_request_id:
            return done(state)
        if state.command_palette is not None and action.invalid_query:
            return done(
                replace(
                    state,
                    command_palette=replace(
                        state.command_palette,
                        grep_search_results=(),
                        grep_search_error_message=action.message,
                    ),
                    pending_grep_search_request_id=None,
                )
            )
        return done(
            replace(
                state,
                notification=NotificationState(level="error", message=action.message),
                pending_grep_search_request_id=None,
            )
        )

    return None
