"""Status bar widget for the initial shell layout."""

from textual.widgets import Static

from plain.models.shell_data import StatusBarState


class StatusBar(Static):
    """Compact one-line summary shown at the bottom of the screen."""

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
        """Build the visible status line."""
        return (
            f"{state.path} | "
            f"{state.item_count} items | "
            f"{state.selected_count} selected | "
            f"sort: {state.sort_label} | "
            f"filter: {state.filter_label}"
        )
