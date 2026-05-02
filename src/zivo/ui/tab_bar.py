"""Tab bar widget shown above the current path bar."""

from rich.style import Style
from rich.text import Text
from textual import events
from textual.message import Message
from textual.widgets import Static

from zivo.models import TabBarState


class TabBar(Static):
    """Compact tab strip for switching between browser workspaces."""

    class TabClicked(Message):
        """Notify the app that a tab was clicked."""

        def __init__(self, tab_index: int) -> None:
            super().__init__()
            self.tab_index = tab_index

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
        self._hovered_index: int | None = None

    def set_state(self, state: TabBarState) -> None:
        """Update the rendered tabs without remounting the widget."""

        self.display = len(state.tabs) > 1
        self._hovered_index = None
        if state == self.state:
            return
        self.state = state
        self.update(self._render_state(state))

    @staticmethod
    def _render_state(state: TabBarState, hovered_index: int | None = None) -> Text:
        rendered = Text(no_wrap=True, overflow="ellipsis")
        for index, tab in enumerate(state.tabs, start=1):
            if index > 1:
                rendered.append(" ")
            if tab.active:
                base_style = Style(reverse=True, bold=True)
            elif hovered_index == index:
                base_style = Style(bold=True, underline=True)
            else:
                base_style = Style(bold=True)
            style = Style(meta={"tab_index": index}) + base_style
            rendered.append(f"[{index}:{tab.label}]", style)
        return rendered

    def on_click(self, event: events.Click) -> None:
        meta = event.style.meta
        tab_index = meta.get("tab_index")
        if tab_index is None:
            return
        event.stop()
        self.post_message(self.TabClicked(tab_index=int(tab_index)))

    def on_mouse_move(self, event: events.MouseMove) -> None:
        meta = event.style.meta
        tab_index = meta.get("tab_index")
        new_hovered = int(tab_index) if tab_index is not None else None
        if new_hovered != self._hovered_index:
            self._hovered_index = new_hovered
            self.update(
                self._render_state(self.state, hovered_index=self._hovered_index)
            )

    def on_leave(self, _event: events.Leave) -> None:
        if self._hovered_index is not None:
            self._hovered_index = None
            self.update(self._render_state(self.state))
