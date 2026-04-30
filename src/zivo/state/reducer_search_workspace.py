"""Search workspace reducers and helpers."""

from dataclasses import replace
from pathlib import Path

from .actions import RequestBrowserSnapshot
from .effects import ReduceResult
from .models import (
    AppState,
    BrowserTabState,
    CurrentPaneDeltaState,
    DirectoryEntryState,
    FilterState,
    GrepSearchResultState,
    HistoryState,
    NotificationState,
    PaneState,
    SearchWorkspaceState,
    select_browser_tabs,
)
from .reducer_common import ReducerFn, finalize, sync_child_pane
from .reducer_navigation_shared import load_browser_tab_from_tabs

_GREP_PATH_SEP = "\x00"


def _encode_grep_path(real_path: str, line_number: int) -> str:
    return f"{real_path}{_GREP_PATH_SEP}{line_number}"


def _decode_grep_path(encoded: str) -> tuple[str, int]:
    real_path, line_str = encoded.rsplit(_GREP_PATH_SEP, 1)
    return real_path, int(line_str)


def _find_grep_result(state: AppState, cursor_path: str) -> GrepSearchResultState | None:
    workspace = state.search_workspace
    if workspace is None or workspace.kind != "grep":
        return None
    for result in workspace.grep_results:
        encoded = _encode_grep_path(result.path, result.line_number)
        if encoded == cursor_path:
            return result
    return None


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
            path=_encode_grep_path(result.path, result.line_number),
            name=result.display_label,
            kind="file",
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
