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
        super().__init__(self._render_text(state), id=id, classes=classes)
        self.state = state

    def set_state(self, state: HelpBarState) -> None:
        """Update the rendered help line."""

        if state == self.state:
            return
        self.state = state
        self.update(self._render_text(state))

    @staticmethod
    def _render_text(state: HelpBarState) -> Text:
        """Render fixed logical rows with tail elision at narrow widths."""

        rendered = Text(no_wrap=True, overflow="ellipsis")
        for index, line in enumerate(state.lines):
            if index:
                rendered.append("\n")
            rendered.append(line)
        return rendered
