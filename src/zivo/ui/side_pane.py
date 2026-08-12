"""Side pane widget for lightweight directory listings."""

from collections.abc import Sequence

from rich.style import Style
from textual import events
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.css.query import NoMatches
from textual.message import Message
from textual.widgets import Label, Static

from zivo.models.shell_data import PaneEntry, PaneStatusViewState

from .pane_rendering import (
    FILE_TYPE_COMPONENT_CLASSES,
    _FileEntryLabelCache,
    _render_file_entries,
    _resolve_component_styles,
)
from .pane_status import render_pane_status
from .resize_debounce import ResizeDebouncer


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
        status: PaneStatusViewState | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes)
        self._title = title
        self._entries = tuple(entries)
        self._status = status
        self._ft_styles: dict[str, Style] = {}
        self._last_render_width = 0
        self._last_clicked_path: str | None = None
        self._hovered_path: str | None = None
        self._label_cache = _FileEntryLabelCache()
        self._resize_debouncer = ResizeDebouncer(
            self,
            self._refresh_after_resize,
            name="side-pane-resize-debounce",
        )

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
                hovered_path=self._hovered_path,
            ),
            id=self.list_view_id,
            classes="pane-list",
        )
        content.can_focus = False
        yield content
        status = Static(
            render_pane_status(self._status),
            id=f"{self.id}-status" if self.id else None,
            classes="pane-status",
        )
        status.display = self._status is not None
        status.can_focus = False
        yield status

    def set_title(self, title: str) -> None:
        """Update the selector-owned pane title without remounting rows."""

        if title == self._title:
            return
        self._title = title
        self.query_one(".pane-title", Label).update(title)

    def set_status(self, status: PaneStatusViewState | None) -> None:
        """Update the explicit side-pane status without remounting rows."""

        if status == self._status:
            return
        self._status = status
        try:
            widget = self.query_one(".pane-status", Static)
        except NoMatches:
            return
        widget.display = status is not None
        widget.update(render_pane_status(status))

    def on_mount(self) -> None:
        self._ft_styles = _resolve_component_styles(self)
        self.call_after_refresh(self._refresh_rendered_labels)

    def on_resize(self, _event: events.Resize) -> None:
        self._resize_debouncer.schedule()

    def on_unmount(self) -> None:
        self._resize_debouncer.stop()

    def _refresh_after_resize(self) -> None:
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
        path = meta.get("entry_path")
        if path is None:
            return
        new_path = str(path)
        if not self._label_cache.contains_path(new_path):
            return
        if new_path != self._hovered_path:
            previous_path = self._hovered_path
            self._hovered_path = new_path
            if not self._refresh_hovered_labels(previous_path, new_path):
                self._refresh_rendered_labels(force=True)

    def on_leave(self, _event: events.Leave) -> None:
        if self._hovered_path is not None:
            previous_path = self._hovered_path
            self._hovered_path = None
            if not self._refresh_hovered_labels(previous_path, None):
                self._refresh_rendered_labels(force=True)

    async def set_entries(self, entries: Sequence[PaneEntry]) -> None:
        """Replace the rendered entries without remounting the pane."""

        next_entries = tuple(entries)
        if next_entries == self._entries:
            return

        content = self._content_widget()
        render_width = self._entry_width(content)
        content.update(
            self._label_cache.rebuild(
                next_entries,
                render_width,
                self._ft_styles,
                selected_directory_style=self.SELECTED_DIRECTORY_STYLE,
                selected_cut_style=self.SELECTED_CUT_STYLE,
                hovered_path=self._hovered_path,
            )
        )
        self._entries = next_entries
        self._last_render_width = render_width

    def _refresh_rendered_labels(self, *, force: bool = False) -> None:
        try:
            content = self._content_widget()
        except NoMatches:
            return
        render_width = self._entry_width(content)
        if render_width <= 0 or (not force and render_width == self._last_render_width):
            return
        content.update(
            self._label_cache.rebuild(
                self._entries,
                render_width,
                self._ft_styles,
                selected_directory_style=self.SELECTED_DIRECTORY_STYLE,
                selected_cut_style=self.SELECTED_CUT_STYLE,
                hovered_path=self._hovered_path,
            )
        )
        self._last_render_width = render_width

    def _refresh_hovered_labels(
        self, previous_path: str | None, next_path: str | None
    ) -> bool:
        try:
            content = self._content_widget()
        except NoMatches:
            return False
        render_width = self._entry_width(content)
        if render_width <= 0:
            return False
        if render_width != self._last_render_width:
            return False
        rendered = self._label_cache.update_hover(
            previous_path,
            next_path,
            self._ft_styles,
            selected_directory_style=self.SELECTED_DIRECTORY_STYLE,
            selected_cut_style=self.SELECTED_CUT_STYLE,
        )
        if rendered is None:
            return False
        content.update(rendered)
        return True

    def _content_widget(self) -> Static:
        return self.query_one(f"#{self.list_view_id}", Static)

    def _entry_width(self, content: Static) -> int:
        return max(0, content.size.width - self.ENTRY_HORIZONTAL_PADDING)

    def refresh_styles(self) -> None:
        """Re-resolve component styles after a theme change."""

        self._ft_styles = _resolve_component_styles(self)
        self._last_render_width = 0
        self._refresh_rendered_labels()
