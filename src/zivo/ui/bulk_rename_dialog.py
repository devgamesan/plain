"""Overlay for reviewing a generated bulk rename plan."""

from rich.text import Text
from textual.containers import Container, Horizontal
from textual.message import Message
from textual.widgets import Button, Static

from zivo.models import BulkRenameDialogState


class BulkRenameDialog(Container):
    """Render the old/new name table and its validation summary."""

    class ActionPressed(Message):
        """Notify the app that a dialog action was clicked."""

        def __init__(self, action_id: str) -> None:
            super().__init__()
            self.action_id = action_id

    def __init__(
        self,
        state: BulkRenameDialogState | None,
        *,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes)
        self.state = state

    def compose(self):
        yield Static("", id="bulk-rename-title")
        yield Static("", id="bulk-rename-summary")
        yield Static("", id="bulk-rename-table")
        yield Static("", id="bulk-rename-base-name")
        yield Static("", id="bulk-rename-status")
        yield Horizontal(
            self._action_button("Rename items", "bulk-rename-apply"),
            self._action_button("Cancel", "bulk-rename-cancel"),
            id="bulk-rename-actions",
        )

    def on_mount(self) -> None:
        self.set_state(self.state)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.id is not None:
            self.post_message(self.ActionPressed(event.button.id))

    def set_state(self, state: BulkRenameDialogState | None) -> None:
        self.state = state
        self.display = state is not None
        if state is None:
            for selector in (
                "#bulk-rename-title",
                "#bulk-rename-summary",
                "#bulk-rename-table",
                "#bulk-rename-base-name",
                "#bulk-rename-status",
            ):
                self.query_one(selector, Static).update("")
            return

        action_fields = {"bulk-rename-apply": "apply", "bulk-rename-cancel": "cancel"}
        for button_id, field in action_fields.items():
            button = self.query_one(f"#{button_id}", Button)
            # Keyboard focus is managed by the reducer. Native Button focus
            # would otherwise add a second, conflicting tab order.
            button.can_focus = False
            button.remove_class("bulk-rename-active")
            if state.active_field == field:
                button.add_class("bulk-rename-active")

        self.query_one("#bulk-rename-title", Static).update(state.title)
        self.query_one("#bulk-rename-summary", Static).update(state.summary)
        self.query_one("#bulk-rename-table", Static).update(self._render_rows(state))
        self.query_one("#bulk-rename-base-name", Static).update(
            self._render_field(
                "Base name",
                state.base_name,
                state.active_field == "base_name",
            )
        )
        status = state.progress or state.result_message or state.error_message or ""
        self.query_one("#bulk-rename-status", Static).update(status)
        self.query_one("#bulk-rename-apply", Button).disabled = not state.apply_enabled

    @staticmethod
    def _action_button(label: str, button_id: str) -> Button:
        button = Button(label, id=button_id)
        # Tab/Enter are dispatched centrally, so these buttons must not
        # participate in Textual's independent DOM focus traversal.
        button.can_focus = False
        return button

    @staticmethod
    def _render_rows(state: BulkRenameDialogState) -> Text:
        text = Text()
        text.append("  Old Name                 New Name                 Status\n", style="bold")
        for row in state.rows:
            status = row.status.title()
            if row.message:
                status += f": {row.message}"
            old_name = row.old_name[:24].ljust(24)
            new_name = row.new_name[:24].ljust(24)
            text.append(f"  {old_name} {new_name} {status}\n")
        text.rstrip()
        return text

    @staticmethod
    def _render_field(label: str, value: str, active: bool) -> Text:
        marker = "> " if active else "  "
        text = Text(f"{marker}{label}: ")
        text.append(value)
        if active:
            text.append("_", style="reverse underline")
            text.stylize("reverse", 0, len(text.plain) - 1)
        return text
