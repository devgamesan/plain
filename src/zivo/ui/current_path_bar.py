"""Current path widget shown at the top of the shell."""

from __future__ import annotations

from pathlib import PurePosixPath, PureWindowsPath

from rich.style import Style
from rich.text import Text
from textual import events
from textual.message import Message
from textual.widgets import Static

from zivo.windows_paths import (
    WINDOWS_DRIVES_LABEL,
    display_path,
    is_windows_drives_root,
    is_windows_path,
    is_search_workspace_path,
)


class CurrentPathBar(Static):
    """Single-line widget that renders the active directory path
    with clickable path segments."""

    class PathSegmentClicked(Message):
        """Posted when a path segment is clicked."""

        def __init__(self, path: str) -> None:
            super().__init__()
            self.path = path

    def __init__(
        self,
        path: str,
        *,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__("", id=id, classes=classes)
        self.path = path
        self._hovered_index: int | None = None
        self._update_content()

    def _update_content(self) -> None:
        self.update(self._render_path(self.path, self._hovered_index))

    @staticmethod
    def _get_path_parts(path: str) -> tuple[str, ...]:
        if is_windows_path(path):
            return PureWindowsPath(path).parts
        return PurePosixPath(path).parts

    @staticmethod
    def _build_cumulative_path(
        path: str,
        parts: tuple[str, ...],
        up_to: int,
    ) -> str:
        if is_windows_path(path):
            return "\\".join(parts[: up_to + 1])
        if up_to == 0:
            return "/"
        return "/" + "/".join(parts[1 : up_to + 1])

    @staticmethod
    def _render_path(
        path: str,
        hovered_index: int | None = None,
    ) -> Text:
        rendered = Text(no_wrap=True, overflow="ellipsis")
        rendered.append("Current Path: ")

        if is_windows_drives_root(path):
            rendered.append(WINDOWS_DRIVES_LABEL)
            return rendered

        if is_search_workspace_path(path):
            rendered.append(display_path(path))
            return rendered

        parts = CurrentPathBar._get_path_parts(path)
        sep = "\\" if is_windows_path(path) else "/"

        for i, part in enumerate(parts):
            cumulative = CurrentPathBar._build_cumulative_path(path, parts, i)
            if i > 1:
                rendered.append(sep)
            base_style = (
                Style(underline=True, bold=True) if hovered_index == i else Style()
            )
            meta_style = Style(
                meta={"path_segment": cumulative, "segment_index": i},
            )
            rendered.append(part, meta_style + base_style)

        return rendered

    def set_path(self, path: str) -> None:
        if path == self.path:
            return
        self.path = path
        self._hovered_index = None
        self._update_content()

    def on_click(self, event: events.Click) -> None:
        meta = event.style.meta
        path = meta.get("path_segment")
        if path is None:
            return
        event.stop()
        self.post_message(self.PathSegmentClicked(path))

    def on_mouse_move(self, event: events.MouseMove) -> None:
        meta = event.style.meta
        index = meta.get("segment_index")
        new_hovered = int(index) if index is not None else None
        if new_hovered != self._hovered_index:
            self._hovered_index = new_hovered
            self._update_content()

    def on_leave(self, _event: events.Leave) -> None:
        if self._hovered_index is not None:
            self._hovered_index = None
            self._update_content()
