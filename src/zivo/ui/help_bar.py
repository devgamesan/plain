"""Help widget shown above the status bar."""

from rich.text import Text
from textual.widgets import Static

from zivo.models import HelpBarState


class HelpBar(Static):
    """Compact help text shown above the status bar."""

    def __init__(
        self,
        state: HelpBarState,
        *,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(Text(state.text), id=id, classes=classes)
        self.state = state

    def set_state(self, state: HelpBarState) -> None:
        """Update the rendered help line."""

        if state == self.state:
            return
        self.state = state
        self.update(Text(state.text))
