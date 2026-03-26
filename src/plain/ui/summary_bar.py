"""Summary bar widget shown near the current pane."""

from textual.widgets import Static

from plain.models.shell_data import CurrentSummaryState


class SummaryBar(Static):
    """Compact one-line summary for the current directory pane."""

    def __init__(
        self,
        state: CurrentSummaryState,
        *,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(self.format_state(state), id=id, classes=classes)
        self.state = state

    @staticmethod
    def format_state(state: CurrentSummaryState) -> str:
        """Build the visible summary line."""

        return (
            f"{state.item_count} items | "
            f"{state.selected_count} selected | "
            f"sort: {state.sort_label}"
        )

    def set_state(self, state: CurrentSummaryState) -> None:
        """Update the rendered line without remounting the widget."""

        if state == self.state:
            return

        self.state = state
        self.update(self.format_state(state))
