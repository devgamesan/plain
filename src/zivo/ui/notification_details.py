"""Notification failure details overlay."""

from rich.style import Style
from rich.text import Text
from textual.containers import Container, VerticalScroll
from textual.message import Message
from textual.widgets import Static

from zivo.models import NotificationDetailsDialogState


class NotificationDetailsDialog(Container):
    """Display failed target paths and reasons from an actionable notification."""

    def __init__(
        self,
        state: NotificationDetailsDialogState | None,
        *,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes)
        self.state = state

    class ActionClicked(Message):
        """Notify the app that a Details recovery action was clicked."""

        def __init__(self, action_id: str, revision: int) -> None:
            super().__init__()
            self.action_id = action_id
            self.revision = revision

    def compose(self):
        yield Static("", id="notification-details-title")
        with VerticalScroll(id="notification-details-lines-scroll"):
            yield Static("", id="notification-details-lines")
        yield Static("", id="notification-details-options")

    def on_mount(self) -> None:
        self.set_state(self.state)

    def set_state(self, state: NotificationDetailsDialogState | None) -> None:
        """Update overlay content and visibility."""

        self.state = state
        self.display = state is not None
        title = self.query_one("#notification-details-title", Static)
        lines = self.query_one("#notification-details-lines", Static)
        options = self.query_one("#notification-details-options", Static)
        if state is None:
            title.update("")
            lines.update("")
            options.update("")
            return
        title.update(state.title)
        rendered = Text()
        for index, line in enumerate(state.lines):
            rendered.append(line)
            if index < len(state.lines) - 1:
                rendered.append("\n")
        lines.update(rendered)
        if state.recovery_action_id and state.recovery_action_shortcut:
            rendered_options = Text("Actions: ")
            rendered_options.append(
                f"{state.recovery_action_shortcut} {state.recovery_action_label}",
                style=Style(
                    bold=True,
                    underline=True,
                    meta={
                        "notification_action_id": state.recovery_action_id,
                        "notification_action_revision": state.recovery_action_revision,
                    },
                ),
            )
            rendered_options.append(" | " + " | ".join(state.options[1:]))
            options.update(rendered_options)
        else:
            options.update(f"Actions: {' | '.join(state.options)}")

    def on_click(self, event) -> None:
        meta = event.style.meta or {}
        action_id = meta.get("notification_action_id")
        revision = meta.get("notification_action_revision")
        if not isinstance(action_id, str) or not isinstance(revision, int):
            return
        event.stop()
        self.post_message(self.ActionClicked(action_id, revision))
