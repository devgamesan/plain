"""Current path widget shown at the top of the shell."""

from __future__ import annotations

from pathlib import PurePosixPath, PureWindowsPath

from rich.style import Style
from rich.text import Text
from textual import events
from textual.message import Message
from textual.widgets import Static

from zivo.models import PathBarState
from zivo.windows_paths import (
    WINDOWS_DRIVES_LABEL,
    display_path,
    is_search_workspace_path,
    is_windows_drives_root,
    is_windows_path,
)


class CurrentPathBar(Static):
    """Single-line widget that renders the active directory path
    with clickable path segments."""

    class PathSegmentClicked(Message):
        """Posted when a path segment is clicked."""

        def __init__(self, path: str) -> None:
            super().__init__()
            self.path = path

    class PathNavigationClicked(Message):
        """Posted when a history navigation affordance is clicked."""

        def __init__(self, direction: str) -> None:
            super().__init__()
            self.direction = direction

    def __init__(
        self,
        path: str,
        *,
        state: PathBarState | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__("", id=id, classes=classes)
        self.path = path
        self._legacy_render = state is None
        self._path_state = state or PathBarState(path=path, show_history_controls=False)
        self._hovered_index: int | None = None
        self._update_content()

    def _update_content(self) -> None:
        if self._legacy_render:
            self.update(self._render_path(self.path, self._hovered_index))
            return
        width = self.size.width
        self.update(
            self._render_path_state(
                self._path_state,
                hovered_index=self._hovered_index,
                max_width=width if width > 0 else None,
            )
        )

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

    @staticmethod
    def _render_path_state(
        state: PathBarState,
        *,
        hovered_index: int | None = None,
        max_width: int | None = None,
    ) -> Text:
        """Render the discoverable path bar while keeping metadata on actions."""

        path = state.path
        rendered = Text(no_wrap=True, overflow="ellipsis")
        if state.show_history_controls:
            for direction, label, enabled in (
                ("back", "[‹]", state.can_go_back),
                ("forward", "[›]", state.can_go_forward),
            ):
                if len(rendered.plain) > 0:
                    rendered.append(" ")
                style = Style(
                    meta={
                        "path_navigation": direction,
                        "navigation_enabled": enabled,
                    },
                    dim=not enabled,
                    bold=enabled,
                )
                rendered.append(label, style)
            rendered.append("  ")

        if is_windows_drives_root(path):
            rendered.append(WINDOWS_DRIVES_LABEL)
            return rendered

        if is_search_workspace_path(path):
            rendered.append(f"Search Workspace: {display_path(path)}")
            return rendered

        parts = CurrentPathBar._get_path_parts(path)
        sep = "\\" if is_windows_path(path) else " › "
        prefix = "Current Path: "
        full_labels = [part for part in parts]
        if not full_labels:
            rendered.append(prefix)
            return rendered

        # Keep the old textual prefix while making the segment boundaries
        # explicit. It remains useful in screenshots and screen-reader output.
        rendered.append(prefix)
        available = None
        if max_width is not None:
            available = max(1, max_width - len(rendered.plain))
        visible_indices = list(range(len(parts)))
        if available is not None:
            def _label_width(indices: list[int]) -> int:
                return len(sep.join(full_labels[index] for index in indices))

            while len(visible_indices) > 2 and _label_width(visible_indices) > available:
                visible_indices.pop(1)

        if len(visible_indices) < len(parts):
            visible_indices = [visible_indices[0], -1, visible_indices[-1]]

        for position, index in enumerate(visible_indices):
            if position:
                rendered.append(sep)
            if index == -1:
                rendered.append("…")
                continue
            cumulative = CurrentPathBar._build_cumulative_path(path, parts, index)
            base_style = (
                Style(underline=True, bold=True)
                if hovered_index == index
                else Style()
            )
            meta_style = Style(
                meta={"path_segment": cumulative, "segment_index": index},
            )
            rendered.append(parts[index], meta_style + base_style)
        return rendered

    def set_state(self, state: PathBarState) -> None:
        """Update path and navigation affordances without remounting."""

        if state == self._path_state:
            return
        self._legacy_render = False
        self._path_state = state
        self.path = state.path
        self._hovered_index = None
        self._update_content()

    def set_path(self, path: str) -> None:
        if path == self.path and path == self._path_state.path:
            return
        if self._legacy_render:
            self.path = path
            self._path_state = PathBarState(path=path, show_history_controls=False)
            self._hovered_index = None
            self._update_content()
            return
        self.set_state(
            PathBarState(
                path=path,
                can_go_back=self._path_state.can_go_back,
                can_go_forward=self._path_state.can_go_forward,
                show_history_controls=self._path_state.show_history_controls,
            )
        )

    def on_click(self, event: events.Click) -> None:
        meta = event.style.meta
        direction = meta.get("path_navigation")
        if direction is not None:
            if not meta.get("navigation_enabled", False):
                return
            event.stop()
            self.post_message(self.PathNavigationClicked(str(direction)))
            return
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

    def on_resize(self, _event: events.Resize) -> None:
        """Recalculate breadcrumb elision after a terminal resize."""

        if not self._legacy_render:
            self._update_content()
