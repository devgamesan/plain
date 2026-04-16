"""Shell widget assembly and refresh helpers."""

from typing import Any

from textual.containers import Container, Horizontal, Vertical
from textual.css.query import NoMatches

from zivo.models import ThreePaneShellData
from zivo.services import SplitTerminalSession
from zivo.state import AppState
from zivo.ui import (
    AttributeDialog,
    ChildPane,
    CommandPalette,
    ConfigDialog,
    ConflictDialog,
    CurrentPathBar,
    HelpBar,
    MainPane,
    ShellCommandDialog,
    SidePane,
    SplitTerminalPane,
    StatusBar,
    TabBar,
)


def build_body(shell: ThreePaneShellData, *, terminal_position: str = "bottom") -> Vertical:
    browser_row_children: list[Any] = [
        SidePane(
            "Parent Directory",
            shell.parent_entries,
            id="parent-pane",
            classes="pane side-pane",
        ),
        MainPane(
            "Current Directory",
            shell.current_entries or (),
            summary=shell.current_summary,
            cursor_index=shell.current_cursor_index,
            cursor_visible=shell.current_cursor_visible,
            context_input=shell.current_context_input,
            id="current-pane",
            classes="pane main-pane",
        ),
        ChildPane(
            shell.child_pane,
            id="child-pane",
            classes="pane side-pane",
        ),
    ]
    body_children: list[Any] = [
        Horizontal(*browser_row_children, id="browser-row"),
    ]
    if terminal_position == "right":
        browser_row_children.append(
            SplitTerminalPane(
                shell.split_terminal,
                id="split-terminal",
                classes="split-terminal-right",
            )
        )
    else:
        body_children.append(
            SplitTerminalPane(shell.split_terminal, id="split-terminal")
        )
    return Vertical(*body_children, id="body")


async def refresh_shell(
    app: Any,
    app_state: AppState,
    shell: ThreePaneShellData,
    split_terminal_session: SplitTerminalSession | None,
    *,
    theme_changed: bool = False,
) -> None:
    try:
        tab_bar = app.query_one("#tab-bar", TabBar)
        current_path_bar = app.query_one("#current-path-bar", CurrentPathBar)
        parent_pane = app.query_one("#parent-pane", SidePane)
        current_pane = app.query_one("#current-pane", MainPane)
        child_pane = app.query_one("#child-pane", ChildPane)
        split_terminal = app.query_one("#split-terminal", SplitTerminalPane)
        command_palette = app.query_one("#command-palette", CommandPalette)
        help_bar = app.query_one("#help-bar", HelpBar)
        status_bar = app.query_one("#status-bar", StatusBar)
        command_palette_layer = app.query_one("#command-palette-layer", Container)
        conflict_dialog_layer = app.query_one("#conflict-dialog-layer", Container)
        attribute_dialog_layer = app.query_one("#attribute-dialog-layer", Container)
        config_dialog_layer = app.query_one("#config-dialog-layer", Container)
        shell_command_dialog_layer = app.query_one("#shell-command-dialog-layer", Container)
        conflict_dialog = app.query_one("#conflict-dialog", ConflictDialog)
        attribute_dialog = app.query_one("#attribute-dialog", AttributeDialog)
        config_dialog = app.query_one("#config-dialog", ConfigDialog)
        shell_command_dialog = app.query_one("#shell-command-dialog", ShellCommandDialog)
    except NoMatches:
        selectors = (
            "#current-path-bar",
            "#tab-bar",
            "#body",
            "#command-palette",
            "#command-palette-layer",
            "#split-terminal",
            "#help-bar",
            "#status-bar",
            "#conflict-dialog",
            "#conflict-dialog-layer",
            "#attribute-dialog",
            "#attribute-dialog-layer",
            "#config-dialog",
            "#config-dialog-layer",
            "#shell-command-dialog",
            "#shell-command-dialog-layer",
        )
        for selector in selectors:
            try:
                await app.query_one(selector).remove()
            except NoMatches:
                pass
        await app.mount(TabBar(shell.tab_bar, id="tab-bar"))
        await app.mount(CurrentPathBar(shell.current_path, id="current-path-bar"))
        terminal_position = app_state.config.display.split_terminal_position
        await app.mount(build_body(shell, terminal_position=terminal_position))
        await app.mount(
            Container(
                CommandPalette(shell.command_palette, id="command-palette"),
                id="command-palette-layer",
                classes="overlay-layer",
            )
        )
        await app.mount(
            Container(
                ConflictDialog(shell.conflict_dialog, id="conflict-dialog"),
                id="conflict-dialog-layer",
                classes="overlay-layer dialog-layer",
            )
        )
        await app.mount(
            Container(
                AttributeDialog(shell.attribute_dialog, id="attribute-dialog"),
                id="attribute-dialog-layer",
                classes="overlay-layer dialog-layer",
            )
        )
        await app.mount(
            Container(
                ConfigDialog(shell.config_dialog, id="config-dialog"),
                id="config-dialog-layer",
                classes="overlay-layer dialog-layer",
            )
        )
        await app.mount(
            Container(
                ShellCommandDialog(shell.shell_command_dialog, id="shell-command-dialog"),
                id="shell-command-dialog-layer",
                classes="overlay-layer dialog-layer",
            )
        )
        await app.mount(HelpBar(shell.help, id="help-bar"))
        await app.mount(StatusBar(shell.status, id="status-bar"))
        return

    tab_bar.set_state(shell.tab_bar)
    current_path_bar.set_path(shell.current_path)
    if shell.current_pane_update.mode == "size_delta":
        current_pane.apply_size_updates(shell.current_pane_update.size_updates)
    elif shell.current_pane_update.mode == "row_delta":
        current_pane.apply_row_updates(shell.current_pane_update.row_updates)
    else:
        current_pane.set_entries(shell.current_entries or (), shell.current_cursor_index)
    current_pane.set_cursor_state(
        shell.current_cursor_index,
        shell.current_cursor_visible,
        force_sync=True,
    )
    current_pane.set_summary(shell.current_summary)
    current_pane.set_context_input(shell.current_context_input)
    await parent_pane.set_entries(shell.parent_entries)
    await child_pane.set_state(shell.child_pane)
    terminal_position = app_state.config.display.split_terminal_position
    if terminal_position == "right":
        child_pane.display = not app_state.split_terminal.visible
    if theme_changed:
        def _refresh_themed_panes() -> None:
            parent_pane.refresh_styles()
            current_pane.refresh_styles()
            child_pane.refresh_styles()

        app.call_after_refresh(_refresh_themed_panes)
    split_terminal.set_state(shell.split_terminal)
    resize_split_terminal_session(app, app_state, split_terminal_session)
    command_palette_layer.display = shell.command_palette is not None
    command_palette.set_state(shell.command_palette)
    help_bar.set_state(shell.help)
    help_bar.display = (
        app_state.show_help_bar
        or shell.command_palette is not None
        or app_state.split_terminal.visible
    )
    status_bar.set_state(shell.status)
    conflict_dialog_layer.display = shell.conflict_dialog is not None
    conflict_dialog.set_state(shell.conflict_dialog)
    attribute_dialog_layer.display = shell.attribute_dialog is not None
    attribute_dialog.set_state(shell.attribute_dialog)
    config_dialog_layer.display = shell.config_dialog is not None
    config_dialog.set_state(shell.config_dialog)
    shell_command_dialog_layer.display = shell.shell_command_dialog is not None
    shell_command_dialog.set_state(shell.shell_command_dialog)

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
