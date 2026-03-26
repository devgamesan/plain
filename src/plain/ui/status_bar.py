"""Status bar widget for the initial shell layout."""

from textual.widgets import Static

from plain.models.shell_data import StatusBarState


class StatusBar(Static):
    """Compact notification line shown at the bottom of the screen."""

    def __init__(
        self,
        state: StatusBarState,
        *,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(self.format_state(state), id=id, classes=classes)
        self.state = state

    @staticmethod
    def format_state(state: StatusBarState) -> str:
        """Build the visible notification line."""

        if not state.message:
            return ""
        label = state.message_level or "message"
        return f"{label}: {state.message}"

    def set_state(self, state: StatusBarState) -> None:
        """Update the rendered line without remounting the widget."""

        if state == self.state:
            return

        self.state = state
        self.update(self.format_state(state))
