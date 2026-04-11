"""Tab bar widget shown above the current path bar."""

from rich.text import Text
from textual.widgets import Static

from peneo.models import TabBarState


class TabBar(Static):
    """Compact tab strip for switching between browser workspaces."""

    def __init__(
        self,
        state: TabBarState,
        *,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(self._render_state(state), id=id, classes=classes)
        self.state = state
        self.display = len(state.tabs) > 1

    def set_state(self, state: TabBarState) -> None:
        """Update the rendered tabs without remounting the widget."""

        self.display = len(state.tabs) > 1
        if state == self.state:
            return
        self.state = state
        self.update(self._render_state(state))

    @staticmethod
    def _render_state(state: TabBarState) -> Text:
        rendered = Text(no_wrap=True, overflow="ellipsis")
        for index, tab in enumerate(state.tabs, start=1):
            if index > 1:
                rendered.append(" ")
            style = "reverse bold" if tab.active else "bold"
            rendered.append(f"[{index}:{tab.label}]", style=style)
        return rendered
