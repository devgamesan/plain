"""Search workspace reducers and helpers."""

from dataclasses import replace

from .effects import ReduceResult
from .models import (
    AppState,
    BrowserTabState,
    CurrentPaneDeltaState,
    DirectoryEntryState,
    FilterState,
    HistoryState,
    NotificationState,
    PaneState,
    SearchWorkspaceState,
    select_browser_tabs,
)
from .reducer_common import ReducerFn, finalize, sync_child_pane
from .reducer_navigation_shared import load_browser_tab_from_tabs
from .search_workspace_helpers import (
    encode_grep_result_path,
    normalize_grep_workspace_path_for_mode,
    normalize_grep_workspace_selected_paths_for_mode,
)


def open_file_search_workspace(
    state: AppState,
    reduce_state: ReducerFn,
) -> ReduceResult:
    """Open file-search results in a new search workspace tab."""

    palette = state.command_palette
    if palette is None or palette.source != "file_search":
        return finalize(state)
    if not palette.file_search_results:
        message = palette.file_search_error_message or "No matching files"
        return finalize(
            replace(
                state,
                notification=NotificationState(level="warning", message=message),
            )
        )

    query = palette.query.strip()
    workspace = SearchWorkspaceState(
        kind="find",
        root_path=state.current_path,
        query=query,
        file_results=palette.file_search_results,
    )
    entries = tuple(
        DirectoryEntryState(
            path=result.path,
            name=result.display_path,
            kind="file",
            size_bytes=result.size_bytes,
            modified_at=result.modified_at,
        )
        for result in workspace.file_results
    )
    cursor_path = entries[0].path if entries else None
    tab = BrowserTabState(
        current_path=workspace.root_path,
        parent_pane=PaneState(directory_path=workspace.root_path, entries=()),
        current_pane=PaneState(
            directory_path=workspace.title,
            entries=entries,
            cursor_path=cursor_path,
        ),
        child_pane=PaneState(directory_path=workspace.root_path, entries=()),
        history=HistoryState(visited_all=(workspace.root_path,)),
        filter=FilterState(),
        current_pane_delta=CurrentPaneDeltaState(),
        search_workspace=workspace,
    )
    tabs = list(select_browser_tabs(state))
    insert_index = state.active_tab_index + 1
    tabs.insert(insert_index, tab)
    next_state = load_browser_tab_from_tabs(
        replace(
            state,
            command_palette=None,
            notification=None,
            ui_mode="BROWSING",
            pending_file_search_request_id=None,
            pending_grep_search_request_id=None,
        ),
        tuple(tabs),
        insert_index,
    )
    return sync_child_pane(next_state, cursor_path, reduce_state)


def open_grep_search_workspace(
    state: AppState,
    reduce_state: ReducerFn,
) -> ReduceResult:
    """Open grep-search results in a new search workspace tab."""

    palette = state.command_palette
    if palette is None or palette.source != "grep_search":
        return finalize(state)
    if not palette.grep_search_results:
        message = palette.grep_search_error_message or "No matching lines"
        return finalize(
            replace(
                state,
                notification=NotificationState(level="warning", message=message),
            )
        )

    query = palette.grep_search_keyword.strip()
    grep_results = palette.grep_search_results
    workspace = SearchWorkspaceState(
        kind="grep",
        root_path=state.current_path,
        query=query,
        grep_results=grep_results,
    )
    entries = tuple(
        DirectoryEntryState(
            path=encode_grep_result_path(result.path, result.line_number),
            name=result.display_label,
            kind="file",
            size_bytes=result.size_bytes,
            modified_at=result.modified_at,
        )
        for result in grep_results
    )
    cursor_path = entries[0].path if entries else None
    tab = BrowserTabState(
        current_path=workspace.root_path,
        parent_pane=PaneState(directory_path=workspace.root_path, entries=()),
        current_pane=PaneState(
            directory_path=workspace.title,
            entries=entries,
            cursor_path=cursor_path,
        ),
        child_pane=PaneState(directory_path=workspace.root_path, entries=()),
        history=HistoryState(visited_all=(workspace.root_path,)),
        filter=FilterState(),
        current_pane_delta=CurrentPaneDeltaState(),
        search_workspace=workspace,
    )
    tabs = list(select_browser_tabs(state))
    insert_index = state.active_tab_index + 1
    tabs.insert(insert_index, tab)
    next_state = load_browser_tab_from_tabs(
        replace(
            state,
            command_palette=None,
            notification=None,
            ui_mode="BROWSING",
            pending_file_search_request_id=None,
            pending_grep_search_request_id=None,
        ),
        tuple(tabs),
        insert_index,
    )
    return sync_child_pane(next_state, cursor_path, reduce_state)


def toggle_grep_search_workspace_display_mode(
    state: AppState,
    reduce_state: ReducerFn,
) -> ReduceResult:
    workspace = state.search_workspace
    if workspace is None or workspace.kind != "grep":
        return finalize(state)

    next_mode = "file" if workspace.grep_display_mode == "match" else "match"
    next_workspace = replace(workspace, grep_display_mode=next_mode)
    next_state = replace(
        state,
        search_workspace=next_workspace,
        current_pane=replace(
            state.current_pane,
            cursor_path=normalize_grep_workspace_path_for_mode(
                next_workspace.grep_results,
                state.current_pane.cursor_path,
                next_mode,
            ),
            selected_paths=normalize_grep_workspace_selected_paths_for_mode(
                next_workspace.grep_results,
                state.current_pane.selected_paths,
                next_mode,
            ),
            selection_anchor_path=normalize_grep_workspace_path_for_mode(
                next_workspace.grep_results,
                state.current_pane.selection_anchor_path,
                next_mode,
            ),
        ),
    )
    return sync_child_pane(next_state, next_state.current_pane.cursor_path, reduce_state)
