"""Side pane widget for lightweight directory listings."""

from collections.abc import Sequence

from rich.style import Style
from textual import events
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.css.query import NoMatches
from textual.message import Message
from textual.widgets import Label, Static

from zivo.models.shell_data import PaneEntry

from .pane_rendering import (
    FILE_TYPE_COMPONENT_CLASSES,
    _render_file_entries,
    _resolve_component_styles,
)


class SidePane(Vertical):
    """Lightweight pane used for parent and child directory listings."""

    COMPONENT_CLASSES = FILE_TYPE_COMPONENT_CLASSES
    ENTRY_HORIZONTAL_PADDING = 2
    SELECTED_DIRECTORY_STYLE = "ft-directory-sel"
    SELECTED_CUT_STYLE = "ft-cut"
    class EntryClicked(Message):
        """Notify the app that a side-pane entry was clicked."""

        def __init__(self, pane_id: str | None, path: str, *, double_click: bool) -> None:
            super().__init__()
            self.pane_id = pane_id
            self.path = path
            self.double_click = double_click

    def __init__(
        self,
        title: str,
        entries: Sequence[PaneEntry],
        *,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes)
        self._title = title
        self._entries = tuple(entries)
        self._ft_styles: dict[str, Style] = {}
        self._last_render_width = 0
        self._last_clicked_path: str | None = None
        self._hovered_path: str | None = None

    @property
    def list_view_id(self) -> str | None:
        """Return the derived list view identifier for tests and styling."""
        return f"{self.id}-list" if self.id else None

    def compose(self) -> ComposeResult:
        yield Label(self._title, classes="pane-title")
        content = Static(
            _render_file_entries(
                self._entries,
                0,
                {},
                selected_directory_style=self.SELECTED_DIRECTORY_STYLE,
                selected_cut_style=self.SELECTED_CUT_STYLE,
            ),
            id=self.list_view_id,
            classes="pane-list",
        )
        content.can_focus = False
        yield content

    def on_mount(self) -> None:
        self._ft_styles = _resolve_component_styles(self)
        self.call_after_refresh(self._refresh_rendered_labels)

    def on_resize(self, _event: events.Resize) -> None:
        self._refresh_rendered_labels()

    def on_click(self, event: events.Click) -> None:
        meta = event.style.meta
        if "entry_path" not in meta:
            return
        path = str(meta["entry_path"])
        double_click = path == self._last_clicked_path
        self._last_clicked_path = path
        event.stop()
        self.post_message(self.EntryClicked(self.id, path, double_click=double_click))

    def on_mouse_move(self, event: events.MouseMove) -> None:
        meta = event.style.meta
        if "entry_path" not in meta:
            if self._hovered_path is not None:
                self._hovered_path = None
                self._refresh_hover()
            return
        path = str(meta["entry_path"])
        if path != self._hovered_path:
            self._hovered_path = path
            self._refresh_hover()

    def on_leave(self, _event: events.Leave) -> None:
        if self._hovered_path is not None:
            self._hovered_path = None
            self._refresh_hover()

    def _refresh_hover(self) -> None:
        try:
            content = self._content_widget()
        except NoMatches:
            return
        render_width = self._last_render_width
        if render_width <= 0:
            return
        content.update(
            _render_file_entries(
                self._entries,
                render_width,
                self._ft_styles,
                selected_directory_style=self.SELECTED_DIRECTORY_STYLE,
                selected_cut_style=self.SELECTED_CUT_STYLE,
                hovered_path=self._hovered_path,
            )
        )

    async def set_entries(self, entries: Sequence[PaneEntry]) -> None:
        """Replace the rendered entries without remounting the pane."""

        next_entries = tuple(entries)
        if next_entries == self._entries:
            return

        self._hovered_path = None
        content = self._content_widget()
        render_width = self._entry_width(content)
        content.update(
            _render_file_entries(
                next_entries,
                render_width,
                self._ft_styles,
                selected_directory_style=self.SELECTED_DIRECTORY_STYLE,
                selected_cut_style=self.SELECTED_CUT_STYLE,
            )
        )
        self._entries = next_entries
        self._last_render_width = render_width

    def _refresh_rendered_labels(self) -> None:
        try:
            content = self._content_widget()
        except NoMatches:
            return
        render_width = self._entry_width(content)
        if render_width <= 0 or render_width == self._last_render_width:
            return
        content.update(
            _render_file_entries(
                self._entries,
                render_width,
                self._ft_styles,
                selected_directory_style=self.SELECTED_DIRECTORY_STYLE,
                selected_cut_style=self.SELECTED_CUT_STYLE,
                hovered_path=self._hovered_path,
            )
        )
        self._last_render_width = render_width

    def _content_widget(self) -> Static:
        return self.query_one(f"#{self.list_view_id}", Static)

    def _entry_width(self, content: Static) -> int:
        return max(0, content.size.width - self.ENTRY_HORIZONTAL_PADDING)

    def refresh_styles(self) -> None:
        """Re-resolve component styles after a theme change."""

        self._ft_styles = _resolve_component_styles(self)
        self._last_render_width = 0
        self._refresh_rendered_labels()
