"""Search workspace reducers and helpers."""

from dataclasses import replace
from pathlib import Path

from .actions import EnterSearchWorkspaceResult, RequestBrowserSnapshot
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


def handle_enter_search_workspace_result(
    state: AppState,
    action: EnterSearchWorkspaceResult,
    reduce_state: ReducerFn,
) -> ReduceResult:
    """Jump from the selected workspace row to the containing directory."""

    del action
    if state.search_workspace is None or state.current_pane.cursor_path is None:
        return finalize(state)

    cursor_path = state.current_pane.cursor_path
    parent_path = str(Path(cursor_path).parent)
    next_state = replace(state, search_workspace=None)
    return reduce_state(
        next_state,
        RequestBrowserSnapshot(parent_path, cursor_path=cursor_path, blocking=True),
    )
