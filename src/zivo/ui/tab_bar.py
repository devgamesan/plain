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

        def __init__(self, index: int) -> None:
            super().__init__()
            self.index = index

    def __init__(
        self,
        state: TabBarState,
        *,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(self._render_state(state), id=id, classes=classes)
        self.state = state
        self._hovered_index: int | None = None
        self.display = len(state.tabs) > 1

    def on_mount(self) -> None:
        self.can_focus = True

    def set_state(self, state: TabBarState) -> None:
        """Update the rendered tabs without remounting the widget."""

        self.display = len(state.tabs) > 1
        if state == self.state:
            return
        self.state = state
        self._hovered_index = None
        self.update(self._render_state(state))

    def on_click(self, event: events.Click) -> None:
        meta = event.style.meta
        if "tab_index" not in meta:
            return
        tab_index = int(meta["tab_index"])
        event.stop()
        self.post_message(self.TabClicked(tab_index))

    def on_mouse_move(self, event: events.MouseMove) -> None:
        meta = event.style.meta
        if "tab_index" not in meta:
            if self._hovered_index is not None:
                self._hovered_index = None
                self.update(self._render_state(self.state))
            return
        tab_index = int(meta["tab_index"])
        if tab_index != self._hovered_index:
            self._hovered_index = tab_index
            self.update(self._render_state(self.state, hovered_index=tab_index))

    def on_leave(self, _event: events.Leave) -> None:
        if self._hovered_index is not None:
            self._hovered_index = None
            self.update(self._render_state(self.state))

    @staticmethod
    def _render_state(state: TabBarState, *, hovered_index: int | None = None) -> Text:
        rendered = Text(no_wrap=True, overflow="ellipsis")
        for index, tab in enumerate(state.tabs, start=1):
            if index > 1:
                rendered.append(" ")
            style = "reverse bold" if tab.active else "bold"
            if hovered_index is not None and (index - 1) == hovered_index and not tab.active:
                style = "reverse bold underline"
            segment = Text(f"[{index}:{tab.label}]", style=style)
            segment.stylize(Style(meta={"tab_index": index - 1}))
            rendered.append(segment)
        return rendered
