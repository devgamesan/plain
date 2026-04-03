"""Shell widget assembly and refresh helpers."""

from typing import Any

from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches

from peneo.models import ThreePaneShellData
from peneo.services import SplitTerminalSession
from peneo.state import AppState
from peneo.ui import (
    AttributeDialog,
    CommandPalette,
    ConfigDialog,
    ConflictDialog,
    CurrentPathBar,
    HelpBar,
    MainPane,
    SidePane,
    SplitTerminalPane,
    StatusBar,
)


def build_body(shell: ThreePaneShellData) -> Vertical:
    return Vertical(
        Horizontal(
            SidePane(
                "Parent Directory",
                shell.parent_entries,
                id="parent-pane",
                classes="pane side-pane",
            ),
            MainPane(
                "Current Directory",
                shell.current_entries,
                summary=shell.current_summary,
                cursor_index=shell.current_cursor_index,
                cursor_visible=shell.current_cursor_visible,
                context_input=shell.current_context_input,
                id="current-pane",
                classes="pane main-pane",
            ),
            SidePane(
                "Child Directory",
                shell.child_entries,
                id="child-pane",
                classes="pane side-pane",
            ),
            id="browser-row",
        ),
        SplitTerminalPane(shell.split_terminal, id="split-terminal"),
        id="body",
    )


async def refresh_shell(
    app: Any,
    app_state: AppState,
    shell: ThreePaneShellData,
    split_terminal_session: SplitTerminalSession | None,
) -> None:
    try:
        current_path_bar = app.query_one("#current-path-bar", CurrentPathBar)
        parent_pane = app.query_one("#parent-pane", SidePane)
        current_pane = app.query_one("#current-pane", MainPane)
        child_pane = app.query_one("#child-pane", SidePane)
        split_terminal = app.query_one("#split-terminal", SplitTerminalPane)
        command_palette = app.query_one("#command-palette", CommandPalette)
        help_bar = app.query_one("#help-bar", HelpBar)
        status_bar = app.query_one("#status-bar", StatusBar)
        conflict_dialog = app.query_one("#conflict-dialog", ConflictDialog)
        attribute_dialog = app.query_one("#attribute-dialog", AttributeDialog)
        config_dialog = app.query_one("#config-dialog", ConfigDialog)
    except NoMatches:
        selectors = (
            "#current-path-bar",
            "#body",
            "#split-terminal",
            "#command-palette",
            "#help-bar",
            "#status-bar",
            "#conflict-dialog",
            "#attribute-dialog",
            "#config-dialog",
        )
        for selector in selectors:
            try:
                await app.query_one(selector).remove()
            except NoMatches:
                pass
        await app.mount(CurrentPathBar(shell.current_path, id="current-path-bar"))
        await app.mount(build_body(shell))
        await app.mount(CommandPalette(shell.command_palette, id="command-palette"))
        await app.mount(HelpBar(shell.help, id="help-bar"))
        await app.mount(StatusBar(shell.status, id="status-bar"))
        await app.mount(ConflictDialog(shell.conflict_dialog, id="conflict-dialog"))
        await app.mount(AttributeDialog(shell.attribute_dialog, id="attribute-dialog"))
        await app.mount(ConfigDialog(shell.config_dialog, id="config-dialog"))
        return

    current_path_bar.set_path(shell.current_path)
    await parent_pane.set_entries(shell.parent_entries)
    current_pane.set_entries(shell.current_entries, shell.current_cursor_index)
    current_pane.set_cursor_state(
        shell.current_cursor_index,
        shell.current_cursor_visible,
        force_sync=True,
    )
    current_pane.set_summary(shell.current_summary)
    current_pane.set_context_input(shell.current_context_input)
    await child_pane.set_entries(shell.child_entries)
    split_terminal.set_state(shell.split_terminal)
    resize_split_terminal_session(app, app_state, split_terminal_session)
    command_palette.set_state(shell.command_palette)
    help_bar.set_state(shell.help)
    status_bar.set_state(shell.status)
    conflict_dialog.set_state(shell.conflict_dialog)
    attribute_dialog.set_state(shell.attribute_dialog)
    config_dialog.set_state(shell.config_dialog)

    if app_state.ui_mode == "BROWSING":
        if app_state.split_terminal.visible and app_state.split_terminal.focus_target == "terminal":
            app.set_focus(split_terminal)
        else:
            try:
                app.set_focus(current_pane.query_one("#current-pane-table"))
            except NoMatches:
                pass


def resize_split_terminal_session(
    app: Any,
    app_state: AppState,
    split_terminal_session: SplitTerminalSession | None,
) -> None:
    if split_terminal_session is None or not app_state.split_terminal.visible:
        return
    try:
        split_terminal = app.query_one("#split-terminal", SplitTerminalPane)
    except NoMatches:
        return
    columns, rows = split_terminal.terminal_dimensions()
    split_terminal_session.resize(columns=columns, rows=rows)
