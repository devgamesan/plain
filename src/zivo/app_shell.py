"""Shell widget assembly and refresh helpers."""

from typing import Any

from textual.containers import Container, Horizontal, Vertical
from textual.css.query import NoMatches
from textual.widgets import DataTable

from zivo.models import ThreePaneShellData
from zivo.state.models import AppState
from zivo.ui import (
    AboutDialog,
    AttributeDialog,
    ChildPane,
    CommandPalette,
    ConfigDialog,
    ConflictDialog,
    CurrentPathBar,
    HelpBar,
    InputDialog,
    MainPane,
    ShellCommandDialog,
    SidePane,
    StatusBar,
    TabBar,
)


def build_body(shell: ThreePaneShellData) -> Vertical:
    if shell.layout_mode == "transfer" and shell.transfer_left and shell.transfer_right:
        parent_pane = SidePane(
            "Parent Directory",
            (),
            id="parent-pane",
            classes="pane side-pane",
        )
        parent_pane.display = False
        child_pane = ChildPane(shell.child_pane, id="child-pane", classes="pane side-pane")
        child_pane.display = False
        browser_row_children: list[Any] = [
            parent_pane,
            MainPane(
                _format_transfer_title(shell.transfer_left),
                shell.transfer_left.entries,
                summary=shell.transfer_left.summary,
                cursor_index=shell.transfer_left.cursor_index,
                cursor_visible=shell.transfer_left.cursor_visible,
                context_input=None,
                id="current-pane",
                classes=_transfer_pane_classes(shell.transfer_left.active),
            ),
            MainPane(
                _format_transfer_title(shell.transfer_right),
                shell.transfer_right.entries,
                summary=shell.transfer_right.summary,
                cursor_index=shell.transfer_right.cursor_index,
                cursor_visible=shell.transfer_right.cursor_visible,
                context_input=None,
                id="transfer-right-pane",
                classes=_transfer_pane_classes(shell.transfer_right.active),
            ),
            child_pane,
        ]
    else:
        browser_row_children = [
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
    return Vertical(*body_children, id="body")


def _format_transfer_title(pane: Any) -> str:
    marker = "ACTIVE" if pane.active else "     "
    return f"[{marker}] {pane.title}: {pane.path}"


def _transfer_pane_classes(active: bool) -> str:
    if active:
        return "pane main-pane transfer-pane active-transfer-pane"
    return "pane main-pane transfer-pane"


async def refresh_shell(
    app: Any,
    app_state: AppState,
    shell: ThreePaneShellData,
    *,
    theme_changed: bool = False,
) -> None:
    try:
        tab_bar = app.query_one("#tab-bar", TabBar)
        current_path_bar = app.query_one("#current-path-bar", CurrentPathBar)
        parent_pane = app.query_one("#parent-pane", SidePane)
        current_pane = app.query_one("#current-pane", MainPane)
        child_pane = app.query_one("#child-pane", ChildPane)
        command_palette = app.query_one("#command-palette", CommandPalette)
        help_bar = app.query_one("#help-bar", HelpBar)
        status_bar = app.query_one("#status-bar", StatusBar)
        command_palette_layer = app.query_one("#command-palette-layer", Container)
        conflict_dialog_layer = app.query_one("#conflict-dialog-layer", Container)
        about_dialog_layer = app.query_one("#about-dialog-layer", Container)
        attribute_dialog_layer = app.query_one("#attribute-dialog-layer", Container)
        config_dialog_layer = app.query_one("#config-dialog-layer", Container)
        shell_command_dialog_layer = app.query_one("#shell-command-dialog-layer", Container)
        input_dialog_layer = app.query_one("#input-dialog-layer", Container)
        conflict_dialog = app.query_one("#conflict-dialog", ConflictDialog)
        about_dialog = app.query_one("#about-dialog", AboutDialog)
        attribute_dialog = app.query_one("#attribute-dialog", AttributeDialog)
        config_dialog = app.query_one("#config-dialog", ConfigDialog)
        shell_command_dialog = app.query_one("#shell-command-dialog", ShellCommandDialog)
        input_dialog = app.query_one("#input-dialog", InputDialog)
    except NoMatches:
        selectors = (
            "#current-path-bar",
            "#tab-bar",
            "#body",
            "#command-palette",
            "#command-palette-layer",
            "#help-bar",
            "#status-bar",
            "#conflict-dialog",
            "#conflict-dialog-layer",
            "#about-dialog",
            "#about-dialog-layer",
            "#attribute-dialog",
            "#attribute-dialog-layer",
            "#config-dialog",
            "#config-dialog-layer",
            "#shell-command-dialog",
            "#shell-command-dialog-layer",
            "#input-dialog",
            "#input-dialog-layer",
        )
        for selector in selectors:
            try:
                await app.query_one(selector).remove()
            except NoMatches:
                pass
        await app.mount(TabBar(shell.tab_bar, id="tab-bar"))
        await app.mount(CurrentPathBar(shell.current_path, id="current-path-bar"))
        await app.mount(build_body(shell))
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
                AboutDialog(shell.about_dialog, id="about-dialog"),
                id="about-dialog-layer",
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
        await app.mount(
            Container(
                InputDialog(shell.input_dialog, id="input-dialog"),
                id="input-dialog-layer",
                classes="overlay-layer dialog-layer",
            )
        )
        await app.mount(HelpBar(shell.help, id="help-bar"))
        await app.mount(StatusBar(shell.status, id="status-bar"))
        return

    if _body_needs_layout_rebuild(app, shell):
        body = app.query_one("#body", Vertical)
        await body.remove()
        await app.mount(
            build_body(shell),
            after="#current-path-bar",
        )
        await refresh_shell(
            app,
            app_state,
            shell,
            theme_changed=theme_changed,
        )
        return

    tab_bar.set_state(shell.tab_bar)
    current_path_bar.set_path(shell.current_path)
    if shell.layout_mode == "transfer" and shell.transfer_left and shell.transfer_right:
        current_pane.set_entries(shell.transfer_left.entries, shell.transfer_left.cursor_index)
        current_pane.set_cursor_state(
            shell.transfer_left.cursor_index,
            shell.transfer_left.cursor_visible,
            force_sync=True,
        )
        current_pane.set_summary(shell.transfer_left.summary)
        current_pane.set_context_input(None)
        current_pane.set_class(shell.transfer_left.active, "active-transfer-pane")
        current_pane.query_one("Label").update(_format_transfer_title(shell.transfer_left))
        try:
            transfer_right_pane = app.query_one("#transfer-right-pane", MainPane)
            transfer_right_pane.set_entries(
                shell.transfer_right.entries,
                shell.transfer_right.cursor_index,
            )
            transfer_right_pane.set_cursor_state(
                shell.transfer_right.cursor_index,
                shell.transfer_right.cursor_visible,
                force_sync=True,
            )
            transfer_right_pane.set_summary(shell.transfer_right.summary)
            transfer_right_pane.set_context_input(None)
            transfer_right_pane.set_class(
                shell.transfer_right.active,
                "active-transfer-pane",
            )
            transfer_right_pane.query_one("Label").update(
                _format_transfer_title(shell.transfer_right)
            )
        except NoMatches:
            pass
    else:
        if shell.current_pane_update.mode == "size_delta":
            current_pane.apply_size_updates(shell.current_pane_update.size_updates)
        elif shell.current_pane_update.mode == "row_delta":
            current_pane.apply_row_updates(shell.current_pane_update.row_updates)
        else:
            current_pane.set_entries(shell.current_entries or (), shell.current_cursor_index)
        current_pane.set_cursor_state(
            shell.current_cursor_index,
            shell.current_cursor_visible,
        )
        current_pane.set_summary(shell.current_summary)
        current_pane.set_context_input(shell.current_context_input)
    await parent_pane.set_entries(shell.parent_entries)
    await child_pane.set_state(shell.child_pane)
    if app_state.layout_mode == "transfer":
        parent_pane.display = False
        child_pane.display = False
    if theme_changed:
        def _refresh_themed_panes() -> None:
            parent_pane.refresh_styles()
            current_pane.refresh_styles()
            child_pane.refresh_styles()

        app.call_after_refresh(_refresh_themed_panes)
    command_palette_layer.display = shell.command_palette is not None
    command_palette.set_state(shell.command_palette)
    help_bar.set_state(shell.help)
    help_bar.display = (
        app_state.show_help_bar
        or shell.command_palette is not None
    )
    status_bar.set_state(shell.status)
    conflict_dialog_layer.display = shell.conflict_dialog is not None
    conflict_dialog.set_state(shell.conflict_dialog)
    about_dialog_layer.display = shell.about_dialog is not None
    about_dialog.set_state(shell.about_dialog)
    attribute_dialog_layer.display = shell.attribute_dialog is not None
    attribute_dialog.set_state(shell.attribute_dialog)
    config_dialog_layer.display = shell.config_dialog is not None
    config_dialog.set_state(shell.config_dialog)
    shell_command_dialog_layer.display = shell.shell_command_dialog is not None
    shell_command_dialog.set_state(shell.shell_command_dialog)
    input_dialog_layer.display = shell.input_dialog is not None
    input_dialog.set_state(shell.input_dialog)

    if app_state.ui_mode == "BROWSING":
        if app_state.layout_mode == "transfer" and app_state.active_transfer_pane == "right":
            try:
                app.set_focus(app.query_one("#transfer-right-pane-table", DataTable))
            except NoMatches:
                pass
        else:
            try:
                app.set_focus(current_pane.query_one("#current-pane-table"))
            except NoMatches:
                pass


def _body_needs_layout_rebuild(app: Any, shell: ThreePaneShellData) -> bool:
    try:
        app.query_one("#transfer-right-pane", MainPane)
        has_transfer_right_pane = True
    except NoMatches:
        has_transfer_right_pane = False
    return (shell.layout_mode == "transfer") != has_transfer_right_pane
