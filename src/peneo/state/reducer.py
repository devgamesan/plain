"""Pure reducer for AppState transitions."""

from dataclasses import replace
from pathlib import Path

from peneo.models import (
    AppConfig,
    CreatePathRequest,
    ExternalLaunchRequest,
    FileMutationResult,
    PasteRequest,
    PasteSummary,
    RenameRequest,
    TrashDeleteRequest,
)

from .actions import (
    Action,
    BeginCommandPalette,
    BeginCreateInput,
    BeginDeleteTargets,
    BeginFilterInput,
    BeginRenameInput,
    BrowserSnapshotFailed,
    BrowserSnapshotLoaded,
    CancelCommandPalette,
    CancelDeleteConfirmation,
    CancelFilterInput,
    CancelPasteConflict,
    CancelPendingInput,
    ChildPaneSnapshotFailed,
    ChildPaneSnapshotLoaded,
    ClearSelection,
    ClipboardPasteCompleted,
    ClipboardPasteFailed,
    ClipboardPasteNeedsResolution,
    ConfigSaveCompleted,
    ConfigSaveFailed,
    ConfirmDeleteTargets,
    ConfirmFilterInput,
    CopyTargets,
    CutTargets,
    CycleConfigEditorValue,
    DismissAttributeDialog,
    DismissConfigEditor,
    DismissNameConflict,
    EnterCursorDirectory,
    ExternalLaunchCompleted,
    ExternalLaunchFailed,
    FileMutationCompleted,
    FileMutationFailed,
    FileSearchCompleted,
    FileSearchFailed,
    FocusSplitTerminal,
    GoToParentDirectory,
    InitializeState,
    MoveCommandPaletteCursor,
    MoveConfigEditorCursor,
    MoveCursor,
    OpenPathInEditor,
    OpenPathWithDefaultApp,
    OpenTerminalAtPath,
    PasteClipboard,
    ReloadDirectory,
    RequestBrowserSnapshot,
    ResolvePasteConflict,
    SaveConfigEditor,
    SendSplitTerminalInput,
    SetCommandPaletteQuery,
    SetCursorPath,
    SetFilterQuery,
    SetNotification,
    SetPendingInputValue,
    SetSort,
    SetUiMode,
    SplitTerminalExited,
    SplitTerminalOutputReceived,
    SplitTerminalStarted,
    SplitTerminalStartFailed,
    SubmitCommandPalette,
    SubmitPendingInput,
    ToggleHiddenFiles,
    ToggleSelection,
    ToggleSelectionAndAdvance,
    ToggleSplitTerminal,
)
from .command_palette import (
    get_command_palette_items,
    normalize_command_palette_cursor,
)
from .effects import (
    CloseSplitTerminalEffect,
    Effect,
    LoadBrowserSnapshotEffect,
    LoadChildPaneSnapshotEffect,
    ReduceResult,
    RunClipboardPasteEffect,
    RunConfigSaveEffect,
    RunExternalLaunchEffect,
    RunFileMutationEffect,
    RunFileSearchEffect,
    StartSplitTerminalEffect,
    WriteSplitTerminalInputEffect,
)
from .models import (
    AppState,
    AttributeInspectionState,
    ClipboardState,
    CommandPaletteState,
    ConfigEditorState,
    DeleteConfirmationState,
    DirectoryEntryState,
    FileSearchResultState,
    NameConflictKind,
    NameConflictState,
    NotificationState,
    PaneState,
    PasteConflictState,
    PendingInputState,
    SortState,
    SplitTerminalState,
)
from .selectors import select_target_paths, select_visible_current_entry_states

_CONFIG_SORT_FIELDS = ("name", "modified", "size")
_CONFIG_THEMES = ("textual-dark", "textual-light")
_CONFIG_PASTE_ACTIONS = ("prompt", "overwrite", "skip", "rename")
_CONFIG_EDITOR_COMMANDS = (None, "nvim", "vim", "nano", "hx", "micro", "emacs -nw")
_REGEX_FILE_SEARCH_PREFIX = "re:"


def reduce_app_state(state: AppState, action: Action) -> ReduceResult:
    """Return a new state after applying a reducer action."""

    def done(next_state: AppState, *effects: Effect) -> ReduceResult:
        return ReduceResult(state=next_state, effects=effects)

    if isinstance(action, InitializeState):
        return done(action.state)

    if isinstance(action, SetUiMode):
        return done(replace(state, ui_mode=action.mode))

    if isinstance(action, BeginFilterInput):
        return done(
            replace(
                state,
                ui_mode="FILTER",
                notification=None,
                pending_input=None,
                command_palette=None,
                pending_file_search_request_id=None,
                delete_confirmation=None,
                name_conflict=None,
                attribute_inspection=None,
            )
        )

    if isinstance(action, ConfirmFilterInput):
        return done(replace(state, ui_mode="BROWSING", notification=None))

    if isinstance(action, CancelFilterInput):
        return done(
            replace(
                state,
                ui_mode="BROWSING",
                filter=replace(state.filter, query="", active=False),
                notification=None,
                pending_input=None,
                command_palette=None,
                delete_confirmation=None,
                name_conflict=None,
                attribute_inspection=None,
            )
        )

    if isinstance(action, BeginRenameInput):
        entry = _current_entry_for_path(state, action.path)
        if entry is None:
            return done(state)
        return done(
            replace(
                state,
                ui_mode="RENAME",
                notification=None,
                pending_input=PendingInputState(
                    prompt="Rename: ",
                    value=entry.name,
                    target_path=entry.path,
                ),
                command_palette=None,
                pending_file_search_request_id=None,
                delete_confirmation=None,
                name_conflict=None,
                attribute_inspection=None,
            )
        )

    if isinstance(action, BeginDeleteTargets):
        if not action.paths:
            return done(state)
        if state.confirm_delete:
            return done(
                replace(
                    state,
                    ui_mode="CONFIRM",
                    notification=None,
                    pending_input=None,
                    command_palette=None,
                    pending_file_search_request_id=None,
                    paste_conflict=None,
                    delete_confirmation=DeleteConfirmationState(paths=action.paths),
                    name_conflict=None,
                    attribute_inspection=None,
                )
            )
        return _run_file_mutation_request(
            replace(
                state,
                notification=None,
                paste_conflict=None,
                delete_confirmation=None,
                name_conflict=None,
                attribute_inspection=None,
            ),
            TrashDeleteRequest(paths=action.paths),
        )

    if isinstance(action, BeginCreateInput):
        prompt = "New file: " if action.kind == "file" else "New directory: "
        return done(
            replace(
                state,
                ui_mode="CREATE",
                notification=None,
                pending_input=PendingInputState(
                    prompt=prompt,
                    create_kind=action.kind,
                ),
                command_palette=None,
                pending_file_search_request_id=None,
                delete_confirmation=None,
                name_conflict=None,
                attribute_inspection=None,
            )
        )

    if isinstance(action, BeginCommandPalette):
        return done(
            replace(
                state,
                ui_mode="PALETTE",
                notification=None,
                pending_input=None,
                command_palette=CommandPaletteState(),
                pending_file_search_request_id=None,
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

    if isinstance(action, DismissConfigEditor):
        return done(
            replace(
                state,
                ui_mode="BROWSING",
                notification=None,
                config_editor=None,
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
                )
            )
        is_regex_query = _is_regex_file_search_query(stripped_query)
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
                        file_search_results=_filter_file_search_results(
                            state.command_palette.file_search_cache_results,
                            normalized_query,
                        ),
                    ),
                    pending_file_search_request_id=None,
                )
            )
        request_id = state.next_request_id
        next_state = replace(
            state,
            command_palette=next_palette,
            pending_file_search_request_id=request_id,
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
        if state.command_palette.source == "file_search":
            results = state.command_palette.file_search_results
            if not results:
                message = (
                    state.command_palette.file_search_error_message
                    or "No matching files"
                )
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
                attribute_inspection=None,
            )
            return reduce_app_state(
                next_state,
                RequestBrowserSnapshot(
                    str(Path(selected_result.path).parent),
                    cursor_path=selected_result.path,
                    blocking=True,
                ),
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
            attribute_inspection=None,
        )
        if selected_item.id == "find_file":
            return done(
                replace(
                    state,
                    notification=None,
                    command_palette=CommandPaletteState(source="file_search"),
                    attribute_inspection=None,
                )
            )
        if selected_item.id == "show_attributes":
            entry = _single_target_entry(state)
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
            return _run_external_launch_request(
                next_state,
                ExternalLaunchRequest(kind="copy_paths", paths=target_paths),
            )
        if selected_item.id == "open_file_manager":
            return reduce_app_state(next_state, OpenPathWithDefaultApp(next_state.current_path))
        if selected_item.id == "open_terminal":
            return reduce_app_state(next_state, OpenTerminalAtPath(next_state.current_path))
        if selected_item.id == "toggle_split_terminal":
            return reduce_app_state(next_state, ToggleSplitTerminal())
        if selected_item.id == "toggle_hidden":
            return reduce_app_state(next_state, ToggleHiddenFiles())
        if selected_item.id == "edit_config":
            return done(
                replace(
                    state,
                    ui_mode="CONFIG",
                    notification=None,
                    command_palette=None,
                    pending_file_search_request_id=None,
                    attribute_inspection=None,
                    config_editor=ConfigEditorState(
                        path=state.config_path,
                        draft=state.config,
                    ),
                )
            )
        if selected_item.id == "create_file":
            return reduce_app_state(next_state, BeginCreateInput("file"))
        if selected_item.id == "create_dir":
            return reduce_app_state(next_state, BeginCreateInput("dir"))
        return done(next_state)

    if isinstance(action, MoveConfigEditorCursor):
        if state.config_editor is None:
            return done(state)
        return done(
            replace(
                state,
                config_editor=replace(
                    state.config_editor,
                    cursor_index=_normalize_config_editor_cursor(
                        state.config_editor.cursor_index + action.delta
                    ),
                ),
            )
        )

    if isinstance(action, CycleConfigEditorValue):
        if state.config_editor is None:
            return done(state)
        next_draft = _cycle_config_editor_value(
            state.config_editor.draft,
            state.config_editor.cursor_index,
            action.delta,
        )
        return done(
            replace(
                state,
                config_editor=replace(
                    state.config_editor,
                    draft=next_draft,
                    dirty=next_draft != state.config,
                ),
            )
        )

    if isinstance(action, SaveConfigEditor):
        if state.config_editor is None:
            return done(state)
        request_id = state.next_request_id
        return done(
            replace(
                state,
                notification=None,
                pending_config_save_request_id=request_id,
                next_request_id=request_id + 1,
            ),
            RunConfigSaveEffect(
                request_id=request_id,
                path=state.config_editor.path,
                config=state.config_editor.draft,
            ),
        )

    if isinstance(action, SetPendingInputValue):
        if state.pending_input is None:
            return done(state)
        return done(
            replace(
                state,
                pending_input=replace(state.pending_input, value=action.value),
            )
        )

    if isinstance(action, CancelPendingInput):
        return done(
            replace(
                state,
                ui_mode="BROWSING",
                notification=None,
                pending_input=None,
                command_palette=None,
                pending_file_search_request_id=None,
                delete_confirmation=None,
                name_conflict=None,
                attribute_inspection=None,
            )
        )

    if isinstance(action, SubmitPendingInput):
        if state.pending_input is None:
            return done(state)
        validation_error = _validate_pending_input(state)
        if validation_error is not None:
            if _is_name_conflict_validation_error(state, validation_error):
                return done(
                    replace(
                        state,
                        ui_mode="CONFIRM",
                        notification=None,
                        paste_conflict=None,
                        delete_confirmation=None,
                        name_conflict=NameConflictState(
                            kind=_name_conflict_kind(state),
                            name=state.pending_input.value,
                        ),
                    )
                )
            return done(
                replace(
                    state,
                    notification=NotificationState(level="error", message=validation_error),
                    name_conflict=None,
                )
            )
        request = _build_file_mutation_request(state)
        if request is None:
            return done(state)
        if isinstance(request, RenameRequest):
            current_name = Path(request.source_path).name
            if current_name == request.new_name:
                return done(
                    replace(
                        state,
                        ui_mode="BROWSING",
                        pending_input=None,
                        notification=NotificationState(level="info", message="Name unchanged"),
                    )
                )
        return _run_file_mutation_request(state, request)

    if isinstance(action, MoveCursor):
        cursor_path = _move_cursor(
            state.current_pane.cursor_path,
            action.visible_paths,
            action.delta,
        )
        next_state = replace(
            state,
            current_pane=replace(state.current_pane, cursor_path=cursor_path),
            notification=None,
        )
        return _sync_child_pane(next_state, cursor_path)

    if isinstance(action, SetCursorPath):
        if action.path is not None and action.path not in _current_entry_paths(state):
            return done(state)
        next_state = replace(
            state,
            current_pane=replace(state.current_pane, cursor_path=action.path),
            notification=None,
        )
        return _sync_child_pane(next_state, action.path)

    if isinstance(action, EnterCursorDirectory):
        entry = _current_entry_for_path(state, state.current_pane.cursor_path)
        if entry is None or entry.kind != "dir":
            return done(state)
        return reduce_app_state(
            state,
            RequestBrowserSnapshot(entry.path, blocking=True),
        )

    if isinstance(action, GoToParentDirectory):
        parent_path = str(Path(state.current_path).parent)
        return reduce_app_state(
            state,
            RequestBrowserSnapshot(
                parent_path,
                cursor_path=state.current_path,
                blocking=True,
            ),
        )

    if isinstance(action, ReloadDirectory):
        return reduce_app_state(
            state,
            RequestBrowserSnapshot(
                state.current_path,
                cursor_path=state.current_pane.cursor_path,
                blocking=True,
            ),
        )

    if isinstance(action, OpenPathWithDefaultApp):
        return _run_external_launch_request(
            replace(state, notification=None),
            ExternalLaunchRequest(kind="open_file", path=action.path),
        )

    if isinstance(action, OpenPathInEditor):
        return _run_external_launch_request(
            replace(state, notification=None),
            ExternalLaunchRequest(kind="open_editor", path=action.path),
        )

    if isinstance(action, OpenTerminalAtPath):
        return _run_external_launch_request(
            replace(state, notification=None),
            ExternalLaunchRequest(kind="open_terminal", path=action.path),
        )

    if isinstance(action, ToggleSplitTerminal):
        if state.split_terminal.visible:
            next_state = replace(
                state,
                split_terminal=SplitTerminalState(),
                notification=None,
            )
            session_id = state.split_terminal.session_id
            if session_id is None:
                return done(next_state)
            return done(next_state, CloseSplitTerminalEffect(session_id=session_id))

        session_id = state.next_request_id
        next_state = replace(
            state,
            notification=None,
            next_request_id=session_id + 1,
            split_terminal=SplitTerminalState(
                visible=True,
                focus_target="terminal",
                status="starting",
                cwd=state.current_path,
                session_id=session_id,
            ),
        )
        return done(
            next_state,
            StartSplitTerminalEffect(session_id=session_id, cwd=state.current_path),
        )

    if isinstance(action, FocusSplitTerminal):
        if not state.split_terminal.visible or state.split_terminal.status != "running":
            return done(state)
        return done(
            replace(
                state,
                notification=None,
                split_terminal=replace(state.split_terminal, focus_target=action.target),
            )
        )

    if isinstance(action, SendSplitTerminalInput):
        session_id = state.split_terminal.session_id
        if (
            not state.split_terminal.visible
            or state.split_terminal.status != "running"
            or session_id is None
        ):
            return done(state)
        return done(
            state,
            WriteSplitTerminalInputEffect(session_id=session_id, data=action.data),
        )

    if isinstance(action, ToggleSelection):
        if action.path not in _current_entry_paths(state):
            return done(state)
        active_entries = _active_current_entries(state)
        selected_paths = set(
            _normalize_selected_paths(
                state.current_pane.selected_paths,
                active_entries,
            )
        )
        if action.path in selected_paths:
            selected_paths.remove(action.path)
        else:
            selected_paths.add(action.path)
        return done(
            replace(
                state,
                current_pane=replace(
                    state.current_pane,
                    selected_paths=frozenset(selected_paths),
                ),
            )
        )

    if isinstance(action, ToggleSelectionAndAdvance):
        if action.path not in _current_entry_paths(state):
            return done(state)
        active_entries = _active_current_entries(state)
        selected_paths = set(
            _normalize_selected_paths(
                state.current_pane.selected_paths,
                active_entries,
            )
        )
        if action.path in selected_paths:
            selected_paths.remove(action.path)
        else:
            selected_paths.add(action.path)
        cursor_path = _move_cursor(action.path, action.visible_paths, 1)
        next_state = replace(
            state,
            current_pane=replace(
                state.current_pane,
                cursor_path=cursor_path,
                selected_paths=frozenset(selected_paths),
            ),
            notification=None,
        )
        return _sync_child_pane(next_state, cursor_path)

    if isinstance(action, ClearSelection):
        return done(
            replace(
                state,
                current_pane=replace(state.current_pane, selected_paths=frozenset()),
            )
        )

    if isinstance(action, CopyTargets):
        if not action.paths:
            return done(
                replace(
                    state,
                    notification=NotificationState(level="warning", message="Nothing to copy"),
                )
            )
        return done(
            replace(
                state,
                clipboard=ClipboardState(mode="copy", paths=action.paths),
                notification=NotificationState(
                    level="info",
                    message=_format_clipboard_message("Copied", action.paths),
                ),
            )
        )

    if isinstance(action, CutTargets):
        if not action.paths:
            return done(
                replace(
                    state,
                    notification=NotificationState(level="warning", message="Nothing to cut"),
                )
            )
        return done(
            replace(
                state,
                clipboard=ClipboardState(mode="cut", paths=action.paths),
                notification=NotificationState(
                    level="info",
                    message=_format_clipboard_message("Cut", action.paths),
                ),
            )
        )

    if isinstance(action, PasteClipboard):
        if state.clipboard.mode == "none" or not state.clipboard.paths:
            return done(
                replace(
                    state,
                    notification=NotificationState(level="warning", message="Clipboard is empty"),
                )
            )

        request = PasteRequest(
            mode=state.clipboard.mode,
            source_paths=state.clipboard.paths,
            destination_dir=state.current_pane.directory_path,
        )
        return _run_paste_request(state, request)

    if isinstance(action, ResolvePasteConflict):
        if state.paste_conflict is None:
            return done(state)
        request = replace(
            state.paste_conflict.request,
            conflict_resolution=action.resolution,
        )
        return _run_paste_request(
            replace(
                state,
                paste_conflict=None,
                delete_confirmation=None,
                command_palette=None,
                ui_mode="BROWSING",
                notification=None,
            ),
            request,
        )

    if isinstance(action, CancelPasteConflict):
        return done(
            replace(
                state,
                paste_conflict=None,
                delete_confirmation=None,
                ui_mode="BROWSING",
                notification=NotificationState(level="warning", message="Paste cancelled"),
            )
        )

    if isinstance(action, ConfirmDeleteTargets):
        if state.delete_confirmation is None:
            return done(state)
        return _run_file_mutation_request(
            replace(
                state,
                delete_confirmation=None,
                paste_conflict=None,
                notification=None,
            ),
            TrashDeleteRequest(paths=state.delete_confirmation.paths),
        )

    if isinstance(action, CancelDeleteConfirmation):
        return done(
            replace(
                state,
                delete_confirmation=None,
                ui_mode="BROWSING",
                notification=NotificationState(level="warning", message="Delete cancelled"),
            )
        )

    if isinstance(action, SetFilterQuery):
        active = bool(action.query) if action.active is None else action.active
        return done(
            replace(
                state,
                filter=replace(state.filter, query=action.query, active=active),
            )
        )

    if isinstance(action, ToggleHiddenFiles):
        next_state = replace(
            state,
            show_hidden=not state.show_hidden,
            notification=NotificationState(
                level="info",
                message="Hidden files shown" if not state.show_hidden else "Hidden files hidden",
            ),
        )
        visible_entries = select_visible_current_entry_states(next_state)
        selected_paths = _normalize_selected_paths(
            state.current_pane.selected_paths,
            visible_entries,
        )
        cursor_path = _normalize_cursor_path(visible_entries, state.current_pane.cursor_path)
        next_state = replace(
            next_state,
            current_pane=replace(
                next_state.current_pane,
                cursor_path=cursor_path,
                selected_paths=selected_paths,
            ),
        )
        return _sync_child_pane(next_state, cursor_path)

    if isinstance(action, SetSort):
        directories_first = state.sort.directories_first
        if action.directories_first is not None:
            directories_first = action.directories_first
        next_state = replace(
            state,
            sort=replace(
                state.sort,
                field=action.field,
                descending=action.descending,
                directories_first=directories_first,
            ),
        )
        cursor_path = _normalize_cursor_path(
            select_visible_current_entry_states(next_state),
            state.current_pane.cursor_path,
        )
        next_state = replace(
            next_state,
            current_pane=replace(
                next_state.current_pane,
                cursor_path=cursor_path,
            )
        )
        return _sync_child_pane(next_state, cursor_path)

    if isinstance(action, SetNotification):
        return done(replace(state, notification=action.notification))

    if isinstance(action, RequestBrowserSnapshot):
        request_id = state.next_request_id
        next_state = replace(
            state,
            notification=None,
            command_palette=None,
            pending_browser_snapshot_request_id=request_id,
            pending_child_pane_request_id=None,
            next_request_id=request_id + 1,
            ui_mode="BUSY" if action.blocking else state.ui_mode,
        )
        return done(
            next_state,
            LoadBrowserSnapshotEffect(
                request_id=request_id,
                path=action.path,
                cursor_path=action.cursor_path,
                blocking=action.blocking,
            ),
        )

    if isinstance(action, BrowserSnapshotLoaded):
        if action.request_id != state.pending_browser_snapshot_request_id:
            return done(state)
        selected_paths = frozenset()
        if action.snapshot.current_path == state.current_path:
            selected_paths = _normalize_selected_paths(
                state.current_pane.selected_paths,
                action.snapshot.current_pane.entries,
            )
        next_state = replace(
            state,
            current_path=action.snapshot.current_path,
            parent_pane=action.snapshot.parent_pane,
            current_pane=replace(
                action.snapshot.current_pane,
                selected_paths=selected_paths,
            ),
            child_pane=action.snapshot.child_pane,
            notification=state.post_reload_notification,
            post_reload_notification=None,
            pending_browser_snapshot_request_id=None,
            pending_child_pane_request_id=None,
            ui_mode="BROWSING" if action.blocking else state.ui_mode,
        )
        return done(next_state)

    if isinstance(action, BrowserSnapshotFailed):
        if action.request_id != state.pending_browser_snapshot_request_id:
            return done(state)
        return done(
            replace(
                state,
                notification=NotificationState(level="error", message=action.message),
                post_reload_notification=None,
                pending_browser_snapshot_request_id=None,
                pending_child_pane_request_id=None,
                ui_mode="BROWSING" if action.blocking else state.ui_mode,
            )
        )

    if isinstance(action, ChildPaneSnapshotLoaded):
        if action.request_id != state.pending_child_pane_request_id:
            return done(state)
        return done(
            replace(
                state,
                child_pane=action.pane,
                notification=None,
                pending_child_pane_request_id=None,
            )
        )

    if isinstance(action, ChildPaneSnapshotFailed):
        if action.request_id != state.pending_child_pane_request_id:
            return done(state)
        return done(
            replace(
                state,
                child_pane=PaneState(directory_path=state.current_path, entries=()),
                notification=NotificationState(level="error", message=action.message),
                pending_child_pane_request_id=None,
            )
        )

    if isinstance(action, ClipboardPasteNeedsResolution):
        if action.request_id != state.pending_paste_request_id or not action.conflicts:
            return done(state)
        if state.paste_conflict_action != "prompt":
            request = replace(
                action.request,
                conflict_resolution=state.paste_conflict_action,
            )
            return _run_paste_request(
                replace(
                    state,
                    paste_conflict=None,
                    delete_confirmation=None,
                    name_conflict=None,
                    notification=None,
                    pending_paste_request_id=None,
                    ui_mode="BROWSING",
                ),
                request,
            )
        return done(
            replace(
                state,
                paste_conflict=PasteConflictState(
                    request=action.request,
                    conflicts=action.conflicts,
                    first_conflict=action.conflicts[0],
                ),
                delete_confirmation=None,
                name_conflict=None,
                pending_paste_request_id=None,
                ui_mode="CONFIRM",
            )
        )

    if isinstance(action, ClipboardPasteCompleted):
        if action.request_id != state.pending_paste_request_id:
            return done(state)

        next_clipboard = state.clipboard
        if state.clipboard.mode == "cut" and action.summary.success_count > 0:
            next_clipboard = ClipboardState()

        next_state = replace(
            state,
            clipboard=next_clipboard,
            notification=None,
            paste_conflict=None,
            delete_confirmation=None,
            name_conflict=None,
            post_reload_notification=_notification_for_paste_summary(action.summary),
            pending_paste_request_id=None,
            ui_mode="BROWSING",
        )
        return _request_snapshot_refresh(next_state)

    if isinstance(action, ClipboardPasteFailed):
        if action.request_id != state.pending_paste_request_id:
            return done(state)
        return done(
            replace(
                state,
                notification=NotificationState(level="error", message=action.message),
                paste_conflict=None,
                delete_confirmation=None,
                name_conflict=None,
                pending_paste_request_id=None,
                ui_mode="BROWSING",
            )
        )

    if isinstance(action, FileSearchCompleted):
        if (
            action.request_id != state.pending_file_search_request_id
            or state.command_palette is None
            or state.command_palette.source != "file_search"
            or state.command_palette.query.strip() != action.query
        ):
            return done(state)
        cache_query = ""
        cache_results: tuple[FileSearchResultState, ...] = ()
        if not _is_regex_file_search_query(action.query):
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

    if isinstance(action, FileMutationCompleted):
        if action.request_id != state.pending_file_mutation_request_id:
            return done(state)
        selected_paths = state.current_pane.selected_paths
        if action.result.removed_paths:
            selected_paths = frozenset(
                path for path in selected_paths if path not in action.result.removed_paths
            )
        next_state = replace(
            state,
            notification=None,
            current_pane=replace(state.current_pane, selected_paths=selected_paths),
            pending_input=None,
            delete_confirmation=None,
            name_conflict=None,
            pending_file_mutation_request_id=None,
            post_reload_notification=NotificationState(
                level=action.result.level,
                message=action.result.message,
            ),
            ui_mode="BROWSING",
        )
        return _request_snapshot_refresh(
            next_state,
            cursor_path=_cursor_path_after_file_mutation(state, action.result),
            keep_current_cursor=not bool(action.result.removed_paths),
        )

    if isinstance(action, FileMutationFailed):
        if action.request_id != state.pending_file_mutation_request_id:
            return done(state)
        return done(
            replace(
                state,
                notification=NotificationState(level="error", message=action.message),
                pending_file_mutation_request_id=None,
                delete_confirmation=None,
                name_conflict=None,
                ui_mode=_restore_ui_mode_after_pending_input(state),
            )
        )

    if isinstance(action, ExternalLaunchCompleted):
        notification = _notification_for_external_launch(action.request)
        if notification is None:
            return done(state)
        return done(replace(state, notification=notification))

    if isinstance(action, ExternalLaunchFailed):
        return done(
            replace(
                state,
                notification=NotificationState(level="error", message=action.message),
            )
        )

    if isinstance(action, SplitTerminalStarted):
        if state.split_terminal.session_id != action.session_id:
            return done(state)
        return done(
            replace(
                state,
                split_terminal=replace(
                    state.split_terminal,
                    status="running",
                    cwd=action.cwd,
                ),
                notification=NotificationState(level="info", message="Split terminal opened"),
            )
        )

    if isinstance(action, SplitTerminalStartFailed):
        if state.split_terminal.session_id != action.session_id:
            return done(state)
        return done(
            replace(
                state,
                split_terminal=SplitTerminalState(),
                notification=NotificationState(level="error", message=action.message),
            )
        )

    if isinstance(action, SplitTerminalOutputReceived):
        return done(state)

    if isinstance(action, SplitTerminalExited):
        if state.split_terminal.session_id != action.session_id:
            return done(state)
        return done(
            replace(
                state,
                split_terminal=SplitTerminalState(),
                notification=NotificationState(
                    level="info",
                    message=_split_terminal_exit_message(action.exit_code),
                ),
            )
        )

    if isinstance(action, ConfigSaveCompleted):
        if state.pending_config_save_request_id != action.request_id:
            return done(state)
        next_config_editor = state.config_editor
        if next_config_editor is not None:
            next_config_editor = replace(
                next_config_editor,
                path=action.path,
                draft=action.config,
                dirty=False,
            )
        return done(
            _apply_config_to_runtime_state(
                replace(
                    state,
                    config=action.config,
                    config_path=action.path,
                    config_editor=next_config_editor,
                    pending_config_save_request_id=None,
                    notification=NotificationState(
                        level="info",
                        message=f"Config saved: {action.path}",
                    ),
                ),
                action.config,
            )
        )

    if isinstance(action, ConfigSaveFailed):
        if state.pending_config_save_request_id != action.request_id:
            return done(state)
        return done(
            replace(
                state,
                pending_config_save_request_id=None,
                notification=NotificationState(
                    level="error",
                    message=f"Failed to save config: {action.message}",
                ),
            )
        )

    if isinstance(action, DismissNameConflict):
        if state.name_conflict is None:
            return done(state)
        return done(
            replace(
                state,
                notification=None,
                name_conflict=None,
                ui_mode=_restore_ui_mode_after_pending_input(state),
            )
        )

    return done(state)


def _current_entry_paths(state: AppState) -> set[str]:
    return {entry.path for entry in _active_current_entries(state)}


def _active_current_entries(state: AppState) -> tuple[DirectoryEntryState, ...]:
    return state.current_pane.entries


def _normalize_selected_paths(
    selected_paths: frozenset[str],
    entries: tuple[DirectoryEntryState, ...],
) -> frozenset[str]:
    entry_paths = {entry.path for entry in entries}
    return frozenset(path for path in selected_paths if path in entry_paths)


def _move_cursor(
    current_path: str | None,
    visible_paths: tuple[str, ...],
    delta: int,
) -> str | None:
    if not visible_paths:
        return None

    if current_path in visible_paths:
        current_index = visible_paths.index(current_path)
    else:
        current_index = 0

    next_index = max(0, min(len(visible_paths) - 1, current_index + delta))
    return visible_paths[next_index]


def _run_paste_request(state: AppState, request: PasteRequest) -> ReduceResult:
    request_id = state.next_request_id
    next_state = replace(
        state,
        notification=None,
        paste_conflict=None,
        delete_confirmation=None,
        pending_paste_request_id=request_id,
        next_request_id=request_id + 1,
        ui_mode="BUSY",
    )
    return ReduceResult(
        state=next_state,
        effects=(RunClipboardPasteEffect(request_id=request_id, request=request),),
    )


def _run_external_launch_request(
    state: AppState,
    request: ExternalLaunchRequest,
) -> ReduceResult:
    request_id = state.next_request_id
    next_state = replace(
        state,
        next_request_id=request_id + 1,
    )
    return ReduceResult(
        state=next_state,
        effects=(RunExternalLaunchEffect(request_id=request_id, request=request),),
    )


def _run_file_mutation_request(
    state: AppState,
    request: RenameRequest | CreatePathRequest | TrashDeleteRequest,
) -> ReduceResult:
    request_id = state.next_request_id
    next_state = replace(
        state,
        notification=None,
        delete_confirmation=None,
        pending_file_mutation_request_id=request_id,
        next_request_id=request_id + 1,
        ui_mode="BUSY",
    )
    return ReduceResult(
        state=next_state,
        effects=(RunFileMutationEffect(request_id=request_id, request=request),),
    )


def _cursor_path_after_file_mutation(
    state: AppState,
    result: FileMutationResult,
) -> str | None:
    active_entries = _active_current_entries(state)
    if result.removed_paths:
        remaining_paths = [
            entry.path
            for entry in active_entries
            if entry.path not in result.removed_paths
        ]
        if not remaining_paths:
            return None
        current_cursor = state.current_pane.cursor_path
        if current_cursor is not None and current_cursor not in result.removed_paths:
            return current_cursor
        original_paths = [entry.path for entry in active_entries]
        if current_cursor in original_paths:
            current_index = original_paths.index(current_cursor)
            if current_index < len(remaining_paths):
                return remaining_paths[current_index]
        return remaining_paths[-1]
    return result.path


def _restore_ui_mode_after_pending_input(state: AppState) -> str:
    if state.pending_input is None:
        return "BROWSING"
    if state.pending_input.create_kind is not None:
        return "CREATE"
    return "RENAME"


def _request_snapshot_refresh(
    state: AppState,
    *,
    cursor_path: str | None = None,
    keep_current_cursor: bool = True,
) -> ReduceResult:
    request_id = state.next_request_id
    next_state = replace(
        state,
        pending_browser_snapshot_request_id=request_id,
        pending_child_pane_request_id=None,
        next_request_id=request_id + 1,
    )
    return ReduceResult(
        state=next_state,
        effects=(
            LoadBrowserSnapshotEffect(
                request_id=request_id,
                path=state.current_path,
                cursor_path=(
                    state.current_pane.cursor_path
                    if keep_current_cursor and cursor_path is None
                    else cursor_path
                ),
                blocking=False,
            ),
        ),
    )


def _sync_child_pane(state: AppState, cursor_path: str | None) -> ReduceResult:
    entry = _current_entry_for_path(state, cursor_path)
    if entry is None or entry.kind != "dir":
        return ReduceResult(
            state=replace(
                state,
                child_pane=PaneState(directory_path=state.current_path, entries=()),
                pending_child_pane_request_id=None,
            )
        )

    if (
        entry.path == state.child_pane.directory_path
        and state.pending_child_pane_request_id is None
    ):
        return ReduceResult(state=state)

    request_id = state.next_request_id
    next_state = replace(
        state,
        pending_child_pane_request_id=request_id,
        next_request_id=request_id + 1,
    )
    return ReduceResult(
        state=next_state,
        effects=(
            LoadChildPaneSnapshotEffect(
                request_id=request_id,
                current_path=state.current_path,
                cursor_path=entry.path,
            ),
        ),
    )


def _current_entry_for_path(
    state: AppState,
    path: str | None,
) -> DirectoryEntryState | None:
    if path is None:
        return None
    for entry in _active_current_entries(state):
        if entry.path == path:
            return entry
    return None


def _single_target_entry(state: AppState) -> DirectoryEntryState | None:
    target_paths = select_target_paths(state)
    if len(target_paths) != 1:
        return None
    return _current_entry_for_path(state, target_paths[0])


def _normalize_cursor_path(
    entries: tuple[DirectoryEntryState, ...],
    current_cursor: str | None,
) -> str | None:
    entry_paths = {entry.path for entry in entries}
    if current_cursor in entry_paths:
        return current_cursor
    if not entries:
        return None
    return entries[0].path


def _normalize_config_editor_cursor(cursor_index: int) -> int:
    return max(0, min(len(_config_editor_labels()) - 1, cursor_index))


def _cycle_config_editor_value(config: AppConfig, cursor_index: int, delta: int) -> AppConfig:
    field_id = _config_editor_field_ids()[_normalize_config_editor_cursor(cursor_index)]
    if field_id == "editor.command":
        return replace(
            config,
            editor=replace(
                config.editor,
                command=_cycle_editor_command(config.editor.command, delta),
            ),
        )
    if field_id == "display.show_hidden_files":
        return replace(
            config,
            display=replace(
                config.display,
                show_hidden_files=not config.display.show_hidden_files,
            ),
        )
    if field_id == "display.theme":
        return replace(
            config,
            display=replace(
                config.display,
                theme=_cycle_choice(
                    _CONFIG_THEMES,
                    config.display.theme,
                    delta,
                ),
            ),
        )
    if field_id == "display.default_sort_field":
        return replace(
            config,
            display=replace(
                config.display,
                default_sort_field=_cycle_choice(
                    _CONFIG_SORT_FIELDS,
                    config.display.default_sort_field,
                    delta,
                ),
            ),
        )
    if field_id == "display.default_sort_descending":
        return replace(
            config,
            display=replace(
                config.display,
                default_sort_descending=not config.display.default_sort_descending,
            ),
        )
    if field_id == "display.directories_first":
        return replace(
            config,
            display=replace(
                config.display,
                directories_first=not config.display.directories_first,
            ),
        )
    if field_id == "behavior.confirm_delete":
        return replace(
            config,
            behavior=replace(
                config.behavior,
                confirm_delete=not config.behavior.confirm_delete,
            ),
        )
    return replace(
        config,
        behavior=replace(
            config.behavior,
            paste_conflict_action=_cycle_choice(
                _CONFIG_PASTE_ACTIONS,
                config.behavior.paste_conflict_action,
                delta,
            ),
        ),
    )


def _cycle_choice(options: tuple[str, ...], current: str, delta: int) -> str:
    current_index = options.index(current) if current in options else 0
    return options[(current_index + delta) % len(options)]


def _cycle_editor_command(current: str | None, delta: int) -> str | None:
    if current in _CONFIG_EDITOR_COMMANDS:
        current_index = _CONFIG_EDITOR_COMMANDS.index(current)
    else:
        current_index = len(_CONFIG_EDITOR_COMMANDS)
    return _CONFIG_EDITOR_COMMANDS[(current_index + delta) % len(_CONFIG_EDITOR_COMMANDS)]


def _config_editor_field_ids() -> tuple[str, ...]:
    return (
        "editor.command",
        "display.show_hidden_files",
        "display.theme",
        "display.default_sort_field",
        "display.default_sort_descending",
        "display.directories_first",
        "behavior.confirm_delete",
        "behavior.paste_conflict_action",
    )


def _config_editor_labels() -> tuple[str, ...]:
    return (
        "Editor command",
        "Show hidden files",
        "Theme",
        "Default sort field",
        "Default sort descending",
        "Directories first",
        "Confirm delete",
        "Paste conflict action",
    )


def _apply_config_to_runtime_state(state: AppState, config: AppConfig) -> AppState:
    return replace(
        state,
        show_hidden=config.display.show_hidden_files,
        sort=SortState(
            field=config.display.default_sort_field,
            descending=config.display.default_sort_descending,
            directories_first=config.display.directories_first,
        ),
        confirm_delete=config.behavior.confirm_delete,
        paste_conflict_action=config.behavior.paste_conflict_action,
    )


def _validate_pending_input(state: AppState) -> str | None:
    if state.pending_input is None:
        return "No input is active"

    name = state.pending_input.value
    if not name:
        return "Name cannot be empty"
    if name in {".", ".."}:
        return "'.' and '..' are not valid names"
    if "/" in name or "\\" in name:
        return "Names cannot include path separators"

    parent_path, current_target_path = _pending_input_parent_and_target(state)
    if parent_path is None:
        return "Unable to resolve target directory"

    candidate_path = str(Path(parent_path) / name)
    existing_paths = _current_entry_paths(state)
    if candidate_path in existing_paths and candidate_path != current_target_path:
        return f"An entry named '{name}' already exists"
    return None


def _is_name_conflict_validation_error(state: AppState, message: str) -> bool:
    return state.pending_input is not None and message == (
        f"An entry named '{state.pending_input.value}' already exists"
    )


def _name_conflict_kind(state: AppState) -> NameConflictKind:
    if state.pending_input is not None and state.pending_input.create_kind == "file":
        return "create_file"
    if state.pending_input is not None and state.pending_input.create_kind == "dir":
        return "create_dir"
    return "rename"


def _build_file_mutation_request(
    state: AppState,
) -> RenameRequest | CreatePathRequest | None:
    if state.pending_input is None:
        return None
    if state.ui_mode == "RENAME" and state.pending_input.target_path is not None:
        return RenameRequest(
            source_path=state.pending_input.target_path,
            new_name=state.pending_input.value,
        )
    if state.ui_mode == "CREATE" and state.pending_input.create_kind is not None:
        return CreatePathRequest(
            parent_dir=state.current_pane.directory_path,
            name=state.pending_input.value,
            kind=state.pending_input.create_kind,
        )
    return None


def _pending_input_parent_and_target(state: AppState) -> tuple[str | None, str | None]:
    if state.pending_input is None:
        return (None, None)
    if state.ui_mode == "RENAME" and state.pending_input.target_path is not None:
        target_path = Path(state.pending_input.target_path)
        return (str(target_path.parent), str(target_path))
    if state.ui_mode == "CREATE":
        return (state.current_pane.directory_path, None)
    return (None, None)


def _filter_file_search_results(
    results: tuple[FileSearchResultState, ...],
    normalized_query: str,
) -> tuple[FileSearchResultState, ...]:
    return tuple(
        result
        for result in results
        if normalized_query in Path(result.path).name.casefold()
    )


def _is_regex_file_search_query(query: str) -> bool:
    return query.strip().startswith(_REGEX_FILE_SEARCH_PREFIX)


def _format_clipboard_message(prefix: str, paths: tuple[str, ...]) -> str:
    noun = "item" if len(paths) == 1 else "items"
    return f"{prefix} {len(paths)} {noun} to clipboard"


def _notification_for_external_launch(
    request: ExternalLaunchRequest,
) -> NotificationState | None:
    if request.kind != "copy_paths":
        return None
    noun = "path" if len(request.paths) == 1 else "paths"
    return NotificationState(
        level="info",
        message=f"Copied {len(request.paths)} {noun} to system clipboard",
    )


def _split_terminal_exit_message(exit_code: int | None) -> str:
    if exit_code is None:
        return "Split terminal closed"
    return f"Split terminal closed (exit {exit_code})"


def _notification_for_paste_summary(summary: PasteSummary) -> NotificationState:
    verb = "Copied" if summary.mode == "copy" else "Moved"
    if summary.failure_count and summary.success_count:
        return NotificationState(
            level="warning",
            message=(
                f"{verb} {summary.success_count}/{summary.total_count} items"
                f" with {summary.failure_count} failure(s)"
            ),
        )
    if summary.failure_count and not summary.success_count and not summary.skipped_count:
        return NotificationState(
            level="error",
            message=f"Failed to {summary.mode} {summary.total_count} item(s)",
        )
    if summary.skipped_count and not summary.success_count and not summary.failure_count:
        return NotificationState(
            level="info",
            message=f"Skipped {summary.skipped_count} conflicting item(s)",
        )
    message = f"{verb} {summary.success_count} item(s)"
    if summary.skipped_count:
        message += f", skipped {summary.skipped_count}"
    return NotificationState(level="info", message=message)
