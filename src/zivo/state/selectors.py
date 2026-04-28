"""Selectors that convert AppState into display models."""

from dataclasses import replace

from zivo.models import CurrentSummaryState, ThreePaneShellData, TransferPaneViewState

from .entry_state_helpers import select_visible_entry_states
from .models import AppState, PaneState, TransferPaneId
from .selectors_panes import (
    CurrentPaneProjection as _CurrentPaneProjection,
)
from .selectors_panes import (
    _project_current_pane_entries,
    _select_current_pane_entries,
    select_child_entries,
    select_current_entries,
    select_current_summary_state,
    select_parent_entries,
    select_tab_bar_state,
)
from .selectors_panes import (
    select_child_pane_for_cursor as _select_child_pane_for_cursor,
)
from .selectors_panes import (
    select_current_pane_update_hint as _select_current_pane_update_hint,
)
from .selectors_shared import (
    _find_current_cursor_index,
    _format_sort_label,
    _has_execute_permission,
    _select_child_syntax_theme,
    _select_command_palette_window,
    compute_current_pane_visible_window,
    compute_search_visible_window,
    get_command_palette_items,
    normalize_command_palette_cursor,
    select_current_entry_for_path,
    select_has_visible_current_entries,
    select_single_target_entry,
    select_target_file_paths,
    select_target_paths,
    select_visible_current_entry_states,
)
from .selectors_ui import (
    select_attribute_dialog_state,
    select_command_palette_state,
    select_config_dialog_state,
    select_conflict_dialog_state,
    select_help_bar_state,
    select_input_bar_state,
    select_input_dialog_state,
    select_shell_command_dialog_state,
    select_status_bar_state,
)

__all__ = [
    "_CurrentPaneProjection",
    "_has_execute_permission",
    "_select_child_syntax_theme",
    "_select_command_palette_window",
    "compute_current_pane_visible_window",
    "compute_search_visible_window",
    "get_command_palette_items",
    "normalize_command_palette_cursor",
    "select_attribute_dialog_state",
    "select_child_entries",
    "select_command_palette_state",
    "select_config_dialog_state",
    "select_conflict_dialog_state",
    "select_current_entries",
    "select_current_entry_for_path",
    "select_current_summary_state",
    "select_has_visible_current_entries",
    "select_help_bar_state",
    "select_input_bar_state",
    "select_input_dialog_state",
    "select_parent_entries",
    "select_shell_command_dialog_state",
    "select_shell_data",
    "select_single_target_entry",
    "select_status_bar_state",
    "select_tab_bar_state",
    "select_target_file_paths",
    "select_target_paths",
    "select_visible_current_entry_states",
]


def select_shell_data(state: AppState) -> ThreePaneShellData:
    """Build the display shell data consumed by the UI layer."""

    current_pane = _select_current_pane_projection(state)
    child_pane = _select_child_pane_for_cursor(state, current_pane.cursor_entry)
    display_directory_sizes = (
        state.config.display.show_directory_sizes or state.sort.field == "size"
    )
    current_pane_update = _select_current_pane_update_hint(
        current_pane.projected_entries,
        state.directory_size_cache,
        display_directory_sizes,
        state.sort,
        state.current_pane.selected_paths,
        frozenset() if state.clipboard.mode != "cut" else frozenset(state.clipboard.paths),
        state.current_pane_delta.changed_paths,
        state.current_pane_delta.revision,
        state.directory_size_delta.changed_paths,
        state.directory_size_delta.revision,
    )
    shell = ThreePaneShellData(
        tab_bar=select_tab_bar_state(state),
        current_path=state.current_path,
        parent_entries=select_parent_entries(state),
        current_entries=(
            _select_current_pane_entries(
                current_pane.projected_entries,
                state.directory_size_cache,
                display_directory_sizes,
                state.current_pane.selected_paths,
                frozenset() if state.clipboard.mode != "cut" else frozenset(state.clipboard.paths),
            )
            if current_pane_update.mode == "full"
            else None
        ),
        child_pane=child_pane,
        current_cursor_index=current_pane.cursor_index,
        current_cursor_visible=state.ui_mode != "FILTER",
        current_pane_update=current_pane_update,
        current_summary=current_pane.summary,
        current_context_input=select_input_bar_state(state),
        help=select_help_bar_state(state),
        command_palette=select_command_palette_state(state),
        status=select_status_bar_state(state),
        conflict_dialog=select_conflict_dialog_state(state),
        attribute_dialog=select_attribute_dialog_state(state),
        config_dialog=select_config_dialog_state(state),
        shell_command_dialog=select_shell_command_dialog_state(state),
        input_dialog=select_input_dialog_state(state),
    )
    if state.layout_mode != "transfer":
        return shell
    return replace(
        shell,
        layout_mode="transfer",
        transfer_left=_select_transfer_pane(state, "left"),
        transfer_right=_select_transfer_pane(state, "right"),
    )


def _select_transfer_pane(
    state: AppState,
    pane_id: TransferPaneId,
) -> TransferPaneViewState | None:
    transfer = state.transfer_left if pane_id == "left" else state.transfer_right
    if transfer is None:
        return None
    visible_entries = _select_visible_transfer_entry_states(state, transfer.pane)
    cursor_index = _find_current_cursor_index(visible_entries, transfer.pane.cursor_path)
    return TransferPaneViewState(
        title="Left Directory" if pane_id == "left" else "Right Directory",
        path=transfer.current_path,
        entries=_select_current_pane_entries(
            visible_entries,
            state.directory_size_cache,
            state.config.display.show_directory_sizes or state.sort.field == "size",
            transfer.pane.selected_paths,
            frozenset() if state.clipboard.mode != "cut" else frozenset(state.clipboard.paths),
        ),
        summary=CurrentSummaryState(
            item_count=len(visible_entries),
            selected_count=len(transfer.pane.selected_paths),
            sort_label=_format_sort_label(state.sort),
        ),
        cursor_index=cursor_index,
        cursor_visible=state.ui_mode != "FILTER",
        active=state.active_transfer_pane == pane_id,
    )


def _select_visible_transfer_entry_states(
    state: AppState,
    pane: PaneState,
):
    return select_visible_entry_states(
        pane.entries,
        state.directory_size_cache,
        state.show_hidden,
        "",
        False,
        state.sort,
    )


def _select_current_pane_projection(state: AppState) -> _CurrentPaneProjection:
    visible_entries = select_visible_current_entry_states(state)
    global_cursor_index = _find_current_cursor_index(
        visible_entries,
        state.current_pane.cursor_path,
    )
    projected_entries, cursor_index = _project_current_pane_entries(
        state,
        visible_entries,
        global_cursor_index,
    )
    cursor_entry = None if global_cursor_index is None else visible_entries[global_cursor_index]
    return _CurrentPaneProjection(
        visible_entries=visible_entries,
        projected_entries=projected_entries,
        cursor_index=cursor_index,
        cursor_entry=cursor_entry,
        summary=select_current_summary_state(state),
    )
