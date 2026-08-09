"""Overlay geometry and pane visibility helpers."""

from dataclasses import replace
from typing import Any

from textual.containers import Container
from textual.css.query import NoMatches

from zivo.state.selectors import select_responsive_pane_layout
from zivo.ui import MainPane


def update_pane_visibility(app: Any, width: int) -> None:
    """Show or hide browser panes based on terminal width and narrow view."""
    try:
        parent_pane = app.query_one("#parent-pane")
        current_pane = app.query_one("#current-pane")
        child_pane = app.query_one("#child-pane")
    except NoMatches:
        return

    layout = select_responsive_pane_layout(replace(app._app_state, terminal_width=width))
    parent_pane.display = layout.show_parent
    current_pane.display = layout.show_current
    child_pane.display = layout.show_child


def get_target_overlay_pane(app: Any) -> Any | None:
    """Get the target pane for overlay positioning based on current mode."""
    if (
        app._app_state.layout_mode == "transfer"
        and app._app_state.active_transfer_pane == "left"
    ):
        try:
            return app.query_one("#transfer-right-pane", MainPane)
        except NoMatches:
            pass

    try:
        current_pane = app.query_one("#current-pane", MainPane)
        if current_pane.display:
            return current_pane
        return app.query_one("#child-pane")
    except NoMatches:
        return None


def update_command_palette_geometry(app: Any) -> None:
    """Constrain the command palette overlay to the appropriate pane."""
    try:
        command_palette_layer = app.query_one("#command-palette-layer", Container)
        browser_row = app.query_one("#browser-row")
    except NoMatches:
        return

    target_pane = get_target_overlay_pane(app)
    if target_pane is None:
        return

    pane_region = target_pane.region
    row_region = browser_row.region
    if pane_region.width <= 0 or pane_region.height <= 0:
        return

    command_palette_layer.styles.width = pane_region.width
    command_palette_layer.styles.height = pane_region.height
    command_palette_layer.styles.offset = (
        pane_region.x,
        row_region.y,
    )


def update_config_dialog_geometry(app: Any) -> None:
    """Constrain the config dialog overlay to the appropriate pane."""
    try:
        config_dialog_layer = app.query_one("#config-dialog-layer", Container)
        browser_row = app.query_one("#browser-row")
    except NoMatches:
        return

    target_pane = get_target_overlay_pane(app)
    if target_pane is None:
        return

    pane_region = target_pane.region
    row_region = browser_row.region
    if pane_region.width <= 0 or pane_region.height <= 0:
        return

    config_dialog_layer.styles.width = pane_region.width
    config_dialog_layer.styles.height = pane_region.height
    config_dialog_layer.styles.offset = (
        pane_region.x,
        row_region.y,
    )


def update_input_dialog_geometry(app: Any) -> None:
    """Constrain the input dialog overlay to the appropriate pane."""
    try:
        input_dialog_layer = app.query_one("#input-dialog-layer", Container)
        browser_row = app.query_one("#browser-row")
    except NoMatches:
        return

    target_pane = get_target_overlay_pane(app)
    if target_pane is None:
        return

    pane_region = target_pane.region
    row_region = browser_row.region
    if pane_region.width <= 0 or pane_region.height <= 0:
        return

    input_dialog_layer.styles.width = pane_region.width
    input_dialog_layer.styles.height = pane_region.height
    input_dialog_layer.styles.offset = (
        pane_region.x,
        row_region.y,
    )


def sync_overlay_layout(app: Any, width: int | None = None) -> None:
    """Refresh side-pane visibility and overlay geometry together."""
    update_pane_visibility(app, app.size.width if width is None else width)
    update_command_palette_geometry(app)
    update_config_dialog_geometry(app)
    update_input_dialog_geometry(app)
