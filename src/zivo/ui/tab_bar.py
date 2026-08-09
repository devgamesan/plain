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

    class TabClosed(Message):
        """Notify the app that a tab close affordance was clicked."""

        def __init__(self, tab_index: int) -> None:
            super().__init__()
            self.tab_index = tab_index

    class NewTabClicked(Message):
        """Notify the app that the new-tab affordance was clicked."""

    def __init__(
        self,
        state: TabBarState,
        *,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(
            self._render_state(state, include_new=True),
            id=id,
            classes=classes,
        )
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
        self.update(self._render_state(state, include_new=True, max_width=self.size.width))

    @staticmethod
    def _render_state(
        state: TabBarState,
        hovered_index: int | None = None,
        *,
        include_new: bool = False,
        max_width: int | None = None,
    ) -> Text:
        rendered = Text(no_wrap=True, overflow="ellipsis")
        if not state.tabs:
            return rendered

        tab_texts = [f"[{index}:{tab.label}]" for index, tab in enumerate(state.tabs, 1)]
        suffix = " [+]" if include_new else ""
        visible = list(range(len(state.tabs)))
        if max_width and max_width > 0:
            full_width = len(" ".join(tab_texts)) + len(suffix)
            if full_width > max_width:
                active_index = next(
                    (index for index, tab in enumerate(state.tabs) if tab.active),
                    0,
                )
                preferred = [active_index]
                if active_index > 0:
                    preferred.append(active_index - 1)
                if active_index + 1 < len(state.tabs):
                    preferred.append(active_index + 1)
                for index in range(len(state.tabs)):
                    if index not in preferred:
                        preferred.append(index)
                visible = []
                for index in preferred:
                    candidate = sorted((*visible, index))
                    overflow_count = len(state.tabs) - len(candidate)
                    candidate_text = " ".join(tab_texts[item] for item in candidate)
                    if overflow_count:
                        candidate_text += f" … (+{overflow_count})"
                    candidate_text += suffix
                    if len(candidate_text) <= max_width or not visible:
                        visible.append(index)
                    if len(visible) >= 3 and len(
                        " ".join(tab_texts[item] for item in visible)
                        + (
                            f" … (+{len(state.tabs) - len(visible)})"
                            if len(visible) < len(state.tabs)
                            else ""
                        )
                        + suffix
                    ) <= max_width:
                        continue
                visible = sorted(set(visible))

        for position, index in enumerate(visible):
            tab = state.tabs[index]
            if position:
                rendered.append(" ")
            display_index = index + 1
            if tab.active:
                base_style = Style(reverse=True, bold=True)
            elif hovered_index == display_index:
                base_style = Style(bold=True, underline=True)
            else:
                base_style = Style(bold=True)
            style = Style(meta={"tab_index": display_index, "tab_action": "activate"}) + base_style
            rendered.append(tab_texts[index], style)
            if hovered_index == display_index:
                rendered.append(" ")
                rendered.append(
                    "×",
                    Style(
                        meta={"tab_close_index": display_index, "tab_action": "close"},
                        bold=True,
                    ),
                )

        if len(visible) < len(state.tabs):
            rendered.append(f" … (+{len(state.tabs) - len(visible)})")
        if include_new:
            rendered.append(" ")
            rendered.append("[+]", Style(meta={"tab_action": "new"}, bold=True))
        return rendered

    def _close_index_at_x(self, x: int) -> int | None:
        """Return a close target for a mouse position when span metadata is absent.

        Some terminals report a mouse move on the edge of a styled cell without
        carrying Rich's span metadata.  Keep the close affordance usable by
        checking the rendered close span at (and immediately beside) that cell.
        """

        content_x = x - int(self.styles.padding.left)
        for candidate in (content_x, content_x - 1, content_x + 1):
            if candidate < 0:
                continue
            for span in self.renderable.spans:
                if not (span.start <= candidate < span.end) or span.style is None:
                    continue
                close_index = span.style.meta.get("tab_close_index")
                if close_index is not None:
                    return int(close_index)
        return None

    def on_click(self, event: events.Click) -> None:
        meta = event.style.meta
        action = meta.get("tab_action")
        if action == "new":
            event.stop()
            self.post_message(self.NewTabClicked())
            return
        close_index = meta.get("tab_close_index")
        if close_index is not None:
            event.stop()
            self.post_message(self.TabClosed(tab_index=int(close_index) - 1))
            return
        tab_index = meta.get("tab_index")
        if tab_index is None:
            close_index = self._close_index_at_x(event.x)
            if close_index is not None:
                event.stop()
                self.post_message(self.TabClosed(tab_index=close_index - 1))
                return
        if tab_index is None:
            return
        event.stop()
        self.post_message(self.TabClicked(tab_index=int(tab_index) - 1))

    def on_mouse_move(self, event: events.MouseMove) -> None:
        meta = event.style.meta
        tab_index = meta.get("tab_index", meta.get("tab_close_index"))
        if tab_index is None:
            close_index = self._close_index_at_x(event.x)
            if close_index is not None:
                tab_index = close_index
        if tab_index is None and self._hovered_index is not None:
            # Preserve the affordance while crossing a cell whose event has no
            # Rich metadata; otherwise the close target disappears before it can
            # be clicked.
            return
        new_hovered = int(tab_index) if tab_index is not None else None
        if new_hovered != self._hovered_index:
            self._hovered_index = new_hovered
            self.update(
                self._render_state(
                    self.state,
                    hovered_index=self._hovered_index,
                    include_new=True,
                    max_width=self.size.width,
                )
            )

    def on_leave(self, _event: events.Leave) -> None:
        if self._hovered_index is not None:
            self._hovered_index = None
            self.update(
                self._render_state(
                    self.state,
                    include_new=True,
                    max_width=self.size.width,
                )
            )

    def on_resize(self, _event: events.Resize) -> None:
        self.update(
            self._render_state(
                self.state,
                hovered_index=self._hovered_index,
                include_new=True,
                max_width=self.size.width,
            )
        )
