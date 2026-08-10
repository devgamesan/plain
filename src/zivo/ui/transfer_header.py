"""Transfer header widget shown above the two transfer panes."""

from rich.text import Text
from textual.widgets import Static

from zivo.models import TransferHeaderState


class TransferHeaderBar(Static):
    """Direction and source/destination summary shown above the transfer panes."""

    def __init__(
        self,
        state: TransferHeaderState | None,
        *,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(self._render_text(state), id=id, classes=classes)
        self.state = state

    def set_state(self, state: TransferHeaderState | None) -> None:
        """Update the rendered transfer summary."""

        if state == self.state:
            return
        self.state = state
        self.update(self._render_text(state))

    @staticmethod
    def _render_text(state: TransferHeaderState | None) -> Text:
        """Render the direction arrow and source/destination/count summary."""

        rendered = Text(no_wrap=True, overflow="ellipsis")
        if state is None:
            return rendered
        arrow = "LEFT → RIGHT" if state.source_side == "left" else "RIGHT → LEFT"
        rendered.append(f"Transfer: {arrow}  ")
        rendered.append(f"src: {state.source_path}  ")
        rendered.append(f"dst: {state.destination_path}  ")
        noun = "item" if state.target_count == 1 else "items"
        rendered.append(f"({state.target_count} {noun} to transfer)")
        return rendered
