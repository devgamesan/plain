"""Notification failure details overlay."""

from rich.text import Text
from textual.containers import Container, VerticalScroll
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
        options.update(f"Actions: {' | '.join(state.options)}")
