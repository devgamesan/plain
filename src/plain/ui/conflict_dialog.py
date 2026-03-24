"""Paste conflict dialog widget."""

from textual.containers import Container
from textual.widgets import Static

from plain.models import ConflictDialogState


class ConflictDialog(Container):
    """Simple overlay used while waiting on paste conflict input."""

    def __init__(
        self,
        state: ConflictDialogState | None,
        *,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes)
        self.state = state

    def compose(self):
        yield Static("", id="conflict-dialog-title")
        yield Static("", id="conflict-dialog-message")
        yield Static("", id="conflict-dialog-options")

    def on_mount(self) -> None:
        self.set_state(self.state)

    def set_state(self, state: ConflictDialogState | None) -> None:
        """Update dialog content and visibility."""

        self.state = state
        self.display = state is not None
        if state is None:
            self.query_one("#conflict-dialog-title", Static).update("")
            self.query_one("#conflict-dialog-message", Static).update("")
            self.query_one("#conflict-dialog-options", Static).update("")
            return

        self.query_one("#conflict-dialog-title", Static).update(state.title)
        self.query_one("#conflict-dialog-message", Static).update(state.message)
        self.query_one("#conflict-dialog-options", Static).update(
            f"Actions: {' | '.join(state.options)}"
        )
