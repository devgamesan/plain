"""Overlay for reviewing and editing a bulk rename plan."""

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
        yield Static("", id="bulk-rename-find")
        yield Static("", id="bulk-rename-replace")
        yield Static("", id="bulk-rename-status")
        yield Horizontal(
            Button("Replace in draft", id="bulk-rename-replace-action"),
            Button("Rename items", id="bulk-rename-apply"),
            Button("Cancel", id="bulk-rename-cancel"),
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
                "#bulk-rename-find",
                "#bulk-rename-replace",
                "#bulk-rename-status",
            ):
                self.query_one(selector, Static).update("")
            return

        self.query_one("#bulk-rename-title", Static).update(state.title)
        self.query_one("#bulk-rename-summary", Static).update(state.summary)
        self.query_one("#bulk-rename-table", Static).update(self._render_rows(state))
        self.query_one("#bulk-rename-find", Static).update(
            self._render_field("Find", state.find_text, state.active_field == "find")
        )
        self.query_one("#bulk-rename-replace", Static).update(
            self._render_field("Replace", state.replace_text, state.active_field == "replace")
        )
        status = state.progress or state.result_message or state.error_message or ""
        self.query_one("#bulk-rename-status", Static).update(status)
        self.query_one("#bulk-rename-replace-action", Button).disabled = not bool(
            state.find_text
        )
        self.query_one("#bulk-rename-apply", Button).disabled = not state.apply_enabled

    @staticmethod
    def _render_rows(state: BulkRenameDialogState) -> Text:
        text = Text()
        text.append("  Old Name                 New Name                 Status\n", style="bold")
        for row in state.rows:
            marker = ">" if row.selected else " "
            status = row.status.title()
            if row.message:
                status += f": {row.message}"
            new_name = row.new_name
            if row.editing:
                new_name = _render_cursor(new_name, row.cursor_pos)
            text.append(f"{marker} {row.old_name:<24.24} {new_name:<24.24} {status}\n")
        text.rstrip()
        return text

    @staticmethod
    def _render_field(label: str, value: str, active: bool) -> Text:
        text = Text(f"{label}: {value}")
        if active:
            text.stylize("reverse")
        return text


def _render_cursor(value: str, cursor_pos: int) -> Text:
    text = Text()
    before = value[:cursor_pos]
    at_cursor = value[cursor_pos] if cursor_pos < len(value) else "_"
    after = value[cursor_pos + 1 :] if cursor_pos < len(value) else ""
    text.append(before)
    text.append(at_cursor, style="reverse underline")
    text.append(after)
    return text
