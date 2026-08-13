"""Child pane widget that toggles between list and preview modes."""

import re
from pathlib import Path as FsPath

from rich.cells import cell_len
from rich.color import Color
from rich.style import Style
from rich.syntax import Syntax
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.css.query import NoMatches
from textual.message import Message
from textual.timer import Timer
from textual.widgets import Label, Static

from zivo.models.shell_data import ChildPaneViewState, MetadataItemViewState
from zivo.services.previews.core import ChafaImagePreviewLoader, ImagePreviewLoader

from .pane_rendering import (
    FILE_TYPE_COMPONENT_CLASSES,
    _FileEntryLabelCache,
    _guess_preview_lexer,
    _render_file_entries,
    _resolve_component_styles,
    truncate_middle,
)
from .pane_status import render_pane_status
from .resize_debounce import ResizeDebouncer
from .side_pane import SidePane, _PaneListScroll

_SGR_SEQUENCE_RE = re.compile(r"\x1b\[([0-9;]*)m")
_KITTY_DELETE_ALL_IMAGES = "\033_Ga=d,d=A\033\\"
_CHAFA_RESIZE_DEBOUNCE_SECONDS = 0.08


class ChildPane(Vertical):
    """Right-side pane that switches between entries and text preview."""

    COMPONENT_CLASSES = FILE_TYPE_COMPONENT_CLASSES
    PREVIEW_HORIZONTAL_PADDING = 2
    SELECTED_DIRECTORY_STYLE = "ft-directory-sel"
    SELECTED_CUT_STYLE = "ft-cut"
    class EntryClicked(Message):
        """Notify the app that a child-pane entry was clicked."""

        def __init__(self, pane_id: str | None, path: str, *, double_click: bool) -> None:
            super().__init__()
            self.pane_id = pane_id
            self.path = path
            self.double_click = double_click

    class PreviewClicked(Message):
        """Notify the app that the preview region was clicked."""

        def __init__(self, pane_id: str | None) -> None:
            super().__init__()
            self.pane_id = pane_id

    class ActionClicked(Message):
        """Notify the app that a fallback action was clicked."""

        def __init__(self, action_id: str) -> None:
            super().__init__()
            self.action_id = action_id

    def __init__(
        self,
        state: ChildPaneViewState,
        *,
        image_preview_loader: ImagePreviewLoader | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes)
        self._state = state
        self._ft_styles: dict[str, Style] = {}
        self._last_render_width = 0
        self._last_render_signature: object | None = None
        self._last_clicked_path: str | None = None
        self._hovered_path: str | None = None
        self._label_cache = _FileEntryLabelCache()
        self._list_expanded = state.scroll_entries is None
        self._list_scroll_context = self._entry_context(
            state.scroll_entries if state.scroll_entries is not None else state.entries
        )
        self._chafa_cached_content: str | None = None
        self._last_chafa_width: int = 0
        self._chafa_resize_timer: Timer | None = None
        self._chafa_resize_request_id = 0
        self._pending_chafa_resize_key: tuple[str, int, str] | None = None
        self._image_preview_loader = image_preview_loader or ChafaImagePreviewLoader()
        self._resize_debouncer = ResizeDebouncer(
            self,
            self._refresh_after_resize,
            name="child-pane-resize-debounce",
        )

    @property
    def list_view_id(self) -> str | None:
        return f"{self.id}-list" if self.id else None

    @property
    def list_scroll_id(self) -> str | None:
        return f"{self.id}-list-scroll" if self.id else None

    @property
    def preview_id(self) -> str | None:
        return f"{self.id}-preview" if self.id else None

    @property
    def preview_scroll_id(self) -> str | None:
        return f"{self.id}-preview-scroll" if self.id else None

    @property
    def preview_help_id(self) -> str | None:
        return f"{self.id}-preview-help" if self.id else None

    @property
    def metadata_bar_id(self) -> str | None:
        return f"{self.id}-metadata-bar" if self.id else None

    def compose(self) -> ComposeResult:
        yield Label(self._state.display_title, classes="pane-title")
        list_content = Static(
            _render_file_entries(
                self._state.entries,
                0,
                {},
                selected_directory_style=self.SELECTED_DIRECTORY_STYLE,
                selected_cut_style=self.SELECTED_CUT_STYLE,
                hovered_path=self._hovered_path,
            ),
            id=self.list_view_id,
            classes="pane-list",
        )
        list_content.can_focus = False
        preview_content = Static(
            self._render_preview(self._state, 0),
            id=self.preview_id,
            classes="pane-preview",
        )
        preview_content.can_focus = False
        preview_scroll = VerticalScroll(
            preview_content,
            id=self.preview_scroll_id,
            classes="pane-preview-scroll",
        )
        preview_scroll.can_focus = True
        preview_scroll.display = self._state.is_preview
        list_content.display = not self._state.is_preview
        preview_help = Label(
            self._state.preview_scroll_hint or "",
            id=self.preview_help_id,
            classes="pane-preview-help",
        )
        preview_help.display = self._state.preview_scroll_hint is not None
        yield _PaneListScroll(
            list_content,
            id=self.list_scroll_id,
            classes="pane-list-scroll",
        )
        yield preview_scroll
        yield preview_help
        metadata_bar = Static(
            self._render_metadata_bar(self._state.metadata_bar, 0),
            id=self.metadata_bar_id,
            classes="pane-metadata-bar",
        )
        metadata_bar.can_focus = False
        yield metadata_bar

    def on_mount(self) -> None:
        self._ft_styles = _resolve_component_styles(self)
        self.call_after_refresh(self._refresh_metadata_bar)
        self.call_after_refresh(self._refresh_rendered_content)

    def on_resize(self, _event: events.Resize) -> None:
        self._resize_debouncer.schedule()

    def _refresh_after_resize(self) -> None:
        self._refresh_metadata_bar()
        self._refresh_rendered_content()

    def on_click(self, event: events.Click) -> None:
        action_id = event.style.meta.get("pane_action_id")
        if action_id is not None:
            event.stop()
            self.post_message(self.ActionClicked(str(action_id)))
            return
        if self._state.is_preview:
            event.stop()
            self.post_message(self.PreviewClicked(self.id))
            return
        meta = event.style.meta
        if "entry_path" not in meta:
            return
        path = str(meta["entry_path"])
        double_click = path == self._last_clicked_path
        self._last_clicked_path = path
        event.stop()
        self.post_message(self.EntryClicked(self.id, path, double_click=double_click))

    def on_mouse_move(self, event: events.MouseMove) -> None:
        if self._state.is_preview:
            return
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
                self._refresh_rendered_content(force=True)

    def on_leave(self, _event: events.Leave) -> None:
        if self._state.is_preview:
            return
        if self._hovered_path is not None:
            previous_path = self._hovered_path
            self._hovered_path = None
            if not self._refresh_hovered_labels(previous_path, None):
                self._refresh_rendered_content(force=True)

    async def set_state(self, state: ChildPaneViewState) -> None:
        if state == self._state:
            return

        previous_state = self._state
        preview_identity_changed = self._preview_identity(state) != self._preview_identity(
            previous_state
        )
        render_signature_changed = self._render_signature(state) != self._render_signature(
            previous_state
        )
        mode_changed = state.is_preview != previous_state.is_preview
        next_scroll_context = self._entry_context(
            state.scroll_entries if state.scroll_entries is not None else state.entries
        )
        list_context_changed = next_scroll_context != self._list_scroll_context
        if list_context_changed or mode_changed:
            self._list_expanded = state.scroll_entries is None
            if list_context_changed:
                self.call_after_refresh(
                    lambda: self.query_one(
                        f"#{self.list_scroll_id}", _PaneListScroll
                    ).scroll_home(animate=False)
                )
        self._list_scroll_context = next_scroll_context
        clear_previous_kitty_preview = self._should_clear_previous_kitty_preview(
            previous_state, state
        )
        self._state = state
        if clear_previous_kitty_preview:
            self.call_after_refresh(self._clear_kitty_content)
        if state.display_title != previous_state.display_title:
            self.query_one(Label).update(state.display_title)
        list_widget = self._list_widget()
        scroll_widget = self._preview_scroll_widget()
        if mode_changed:
            list_widget.display = not state.is_preview
            scroll_widget.display = state.is_preview
        try:
            preview_help = self._preview_help_widget()
        except NoMatches:
            preview_help = None
        if preview_help is not None and (
            state.preview_scroll_hint != previous_state.preview_scroll_hint
            or mode_changed
        ):
            preview_help.update(state.preview_scroll_hint or "")
            preview_help.display = state.preview_scroll_hint is not None
        if state.metadata_bar != previous_state.metadata_bar:
            try:
                self._refresh_metadata_bar(force=True)
            except NoMatches:
                pass
        if render_signature_changed or mode_changed:
            rendered = self._refresh_rendered_content(force=True)
            if not rendered:
                self.call_after_refresh(self._refresh_rendered_content)
        if preview_identity_changed:
            self._invalidate_chafa_resize_requests()
            object.__setattr__(self, "_chafa_cached_content", None)
            object.__setattr__(self, "_last_chafa_width", 0)
            object.__setattr__(self, "_kitty_cached", None)
            object.__setattr__(self, "_last_kitty_path", None)
            object.__setattr__(self, "_last_kitty_width", None)
            if state.is_preview:
                self.call_after_refresh(lambda: scroll_widget.scroll_home(animate=False))

    def on_unmount(self) -> None:
        self._resize_debouncer.stop()
        self._invalidate_chafa_resize_requests()
        if self._state.is_preview and self._state.preview_kind == "kitty":
            self._clear_kitty_content()

    def _refresh_rendered_content(self, *, force: bool = False) -> bool:
        render_signature = self._render_signature(self._state)
        try:
            if self._state.is_preview:
                widget = self._preview_widget()
                render_width = max(0, widget.size.width - self.PREVIEW_HORIZONTAL_PADDING)
                if render_width <= 0:
                    if self._state.status is None:
                        return False
                    widget.update(self._render_preview(self._state, 0))
                    self._last_render_width = render_width
                    self._last_render_signature = render_signature
                    return True
                if (
                    not force
                    and render_width == self._last_render_width
                    and render_signature == self._last_render_signature
                ):
                    return True
                if (
                    self._state.preview_kind == "image"
                    and self._state.preview_path
                    and render_width != self._last_chafa_width
                ):
                    self._schedule_chafa_resize_preview(
                        self._state.preview_path,
                        render_width,
                        "symbols",
                    )

                widget.update(
                    self._render_preview(
                        self._state,
                        render_width,
                        chafa_override=self._chafa_cached_content,
                    )
                )
                self._last_render_width = render_width
                self._last_render_signature = render_signature
                if self._state.preview_kind == "kitty" and self._state.preview_content:
                    captured = self._state.preview_content
                    self.call_after_refresh(
                        lambda c=captured: self._write_kitty_content(c)
                    )
                return True

            widget = self._list_widget()
        except NoMatches:
            return True
        render_width = max(0, widget.size.width - SidePane.ENTRY_HORIZONTAL_PADDING)
        if render_width <= 0:
            return False
        if (
            not force
            and render_width == self._last_render_width
            and render_signature == self._last_render_signature
        ):
            return True
        rendered_entries = (
            self._state.scroll_entries
            if self._list_expanded and self._state.scroll_entries is not None
            else self._state.entries
        )
        widget.update(
            self._label_cache.rebuild(
                rendered_entries,
                render_width,
                self._ft_styles,
                selected_directory_style=self.SELECTED_DIRECTORY_STYLE,
                selected_cut_style=self.SELECTED_CUT_STYLE,
                hovered_path=self._hovered_path,
            )
        )
        self._last_render_width = render_width
        self._last_render_signature = render_signature
        return True

    def _refresh_hovered_labels(
        self, previous_path: str | None, next_path: str | None
    ) -> bool:
        try:
            widget = self._list_widget()
        except NoMatches:
            return False
        render_width = max(0, widget.size.width - SidePane.ENTRY_HORIZONTAL_PADDING)
        if render_width <= 0:
            return False
        if render_width != self._last_render_width:
            return False
        if self._render_signature(self._state) != self._last_render_signature:
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
        widget.update(rendered)
        return True

    def _list_widget(self) -> Static:
        return self.query_one(f"#{self.list_view_id}", Static)

    def _prepare_list_scroll(self) -> bool:
        """Expand the child directory list before its first wheel movement."""

        if self._list_expanded or self._state.scroll_entries is None:
            return False
        self._list_expanded = True
        self._refresh_rendered_content(force=True)
        return True

    @staticmethod
    def _entry_context(entries) -> str | None:
        if not entries:
            return None
        path = entries[0].path.replace("\\", "/")
        return path.rsplit("/", 1)[0] if "/" in path else None

    def _preview_widget(self) -> Static:
        return self.query_one(f"#{self.preview_id}", Static)

    def _preview_scroll_widget(self) -> VerticalScroll:
        return self.query_one(f"#{self.preview_scroll_id}", VerticalScroll)

    def _preview_help_widget(self) -> Label:
        return self.query_one(f"#{self.preview_help_id}", Label)

    def _metadata_bar_widget(self) -> Static:
        return self.query_one(f"#{self.metadata_bar_id}", Static)

    def _refresh_metadata_bar(self, *, force: bool = False) -> bool:
        try:
            widget = self._metadata_bar_widget()
        except NoMatches:
            return False
        render_width = max(0, widget.size.width - 2)
        if render_width <= 0:
            return False
        rendered = self._render_metadata_bar(self._state.metadata_bar, render_width)
        if force or str(widget.renderable) != rendered:
            widget.update(rendered)
        return True

    @staticmethod
    def _render_metadata_bar(
        items: tuple[MetadataItemViewState, ...],
        max_width: int,
    ) -> str:
        """Render one-line attributes, dropping lower-priority items first."""

        if max_width <= 0 or not items:
            return ""
        separator = " · "
        values = [item.value for item in items]
        visible: list[str] = []
        for value in values:
            candidate = separator.join((*visible, value))
            if cell_len(candidate) > max_width:
                break
            visible.append(value)
        if not visible:
            return truncate_middle(values[0], max_width)
        rendered = separator.join(visible)
        if len(visible) < len(values):
            ellipsis = " …"
            if cell_len(rendered + ellipsis) <= max_width:
                return rendered + ellipsis
            return truncate_middle(rendered, max_width)
        return rendered

    def preview_render_width(self) -> int:
        """Return the currently available preview width in terminal cells."""

        try:
            widget = self._preview_widget()
        except NoMatches:
            return 0
        return max(0, widget.size.width - self.PREVIEW_HORIZONTAL_PADDING)

    @staticmethod
    def _render_preview(
        state: ChildPaneViewState,
        render_width: int,
        chafa_override: str | None = None,
    ):
        if state.status is not None:
            return render_pane_status(state.status, state.metadata)

        if state.preview_message is not None:
            return Text(state.preview_message, style="italic dim")

        if state.preview_content is None:
            return Text()

        if state.preview_kind == "image":
            content = chafa_override if chafa_override is not None else state.preview_content
            return _render_image_preview_text(content)

        if state.preview_kind == "kitty":
            return _render_kitty_preview_text(state.preview_content)

        lexer = "text"
        if state.preview_path is not None:
            lexer = _guess_preview_lexer(state.preview_path)

        return Syntax(
            state.preview_content,
            lexer=lexer,
            theme=state.syntax_theme,
            word_wrap=state.preview_word_wrap,
            line_numbers=state.preview_start_line is not None,
            start_line=state.preview_start_line or 1,
            highlight_lines=(
                {state.preview_highlight_line}
                if state.preview_highlight_line is not None
                else None
            ),
            code_width=max(1, render_width),
        )

    def refresh_styles(self) -> None:
        """Re-resolve component styles after a theme change."""

        self._ft_styles = _resolve_component_styles(self)
        self._last_render_width = 0
        self._last_render_signature = None
        self._refresh_rendered_content(force=True)

    def _write_kitty_content(self, content: str) -> None:
        """Write Kitty graphics protocol escape sequence to the terminal.

        Re-runs chafa when the available preview width changes so the
        image always fills the pane without overflowing the terminal.
        """
        try:
            from zivo.services.previews.core import resolve_image_preview_format

            scroll = self._preview_scroll_widget()
            region = scroll.region
            if region.x < 0 or region.y < 0:
                return

            pane_width = max(1, scroll.size.width - 2)

            mode = getattr(self._state, "image_preview_mode", "auto")
            fmt = resolve_image_preview_format(mode)
            if fmt != "kitty":
                return

            path = self._state.preview_path
            last_width = getattr(self, "_last_kitty_width", None)
            last_path = getattr(self, "_last_kitty_path", None)

            if path == last_path and pane_width != last_width and path:
                self._schedule_chafa_resize_preview(
                    path,
                    pane_width,
                    "kitty",
                )
            else:
                cached = getattr(self, "_kitty_cached", None)
                if path == last_path and cached is not None:
                    content = cached

            if not content:
                return

            object.__setattr__(self, "_kitty_cached", content)
            object.__setattr__(self, "_last_kitty_path", path)
            object.__setattr__(self, "_last_kitty_width", pane_width)

            row = region.y + 1
            col = region.x + 1
            write = f"{_KITTY_DELETE_ALL_IMAGES}\033[{row};{col}H{content}"
            self._write_terminal_content(write)
        except Exception:
            pass

    def _schedule_chafa_resize_preview(
        self,
        path: str,
        preview_columns: int,
        image_preview_format: str,
    ) -> None:
        key = (path, preview_columns, image_preview_format)
        if self._pending_chafa_resize_key == key:
            return
        self._chafa_resize_request_id += 1
        request_id = self._chafa_resize_request_id
        self._pending_chafa_resize_key = key
        if self._chafa_resize_timer is not None:
            self._chafa_resize_timer.stop()
        self._chafa_resize_timer = self.set_timer(
            _CHAFA_RESIZE_DEBOUNCE_SECONDS,
            lambda: self._start_chafa_resize_worker(
                request_id,
                path,
                preview_columns,
                image_preview_format,
            ),
            name=f"chafa-resize-debounce:{request_id}",
        )

    def _start_chafa_resize_worker(
        self,
        request_id: int,
        path: str,
        preview_columns: int,
        image_preview_format: str,
    ) -> None:
        self._chafa_resize_timer = None
        if (
            request_id != self._chafa_resize_request_id
            or self._pending_chafa_resize_key
            != (path, preview_columns, image_preview_format)
        ):
            return

        def _load_preview() -> None:
            content: str | None = None
            try:
                result = self._image_preview_loader.load_preview(
                    FsPath(path),
                    preview_columns=preview_columns,
                    image_preview_format=image_preview_format,
                )
                if result and result.content:
                    content = result.content
            except Exception:
                content = None
            try:
                self.app.call_from_thread(
                    self._complete_chafa_resize_request,
                    request_id,
                    path,
                    preview_columns,
                    image_preview_format,
                    content,
                )
            except Exception:
                pass

        self.run_worker(
            _load_preview,
            name=f"chafa-resize:{request_id}",
            group=f"{self.id or 'child-pane'}:chafa-resize",
            description="Regenerate resized image preview",
            exit_on_error=False,
            thread=True,
        )

    def _complete_chafa_resize_request(
        self,
        request_id: int,
        path: str,
        preview_columns: int,
        image_preview_format: str,
        content: str | None,
    ) -> None:
        key = (path, preview_columns, image_preview_format)
        if (
            request_id != self._chafa_resize_request_id
            or self._pending_chafa_resize_key != key
            or self._state.preview_path != path
        ):
            return
        if image_preview_format == "symbols":
            if self._state.preview_kind != "image":
                return
            if content:
                object.__setattr__(self, "_chafa_cached_content", content)
            object.__setattr__(self, "_last_chafa_width", preview_columns)
            self._pending_chafa_resize_key = None
            try:
                widget = self._preview_widget()
            except NoMatches:
                return
            widget.update(
                self._render_preview(
                    self._state,
                    preview_columns,
                    chafa_override=self._chafa_cached_content,
                )
            )
            return

        if image_preview_format != "kitty" or self._state.preview_kind != "kitty":
            return
        if content:
            object.__setattr__(self, "_kitty_cached", content)
        object.__setattr__(self, "_last_kitty_path", path)
        object.__setattr__(self, "_last_kitty_width", preview_columns)
        self._pending_chafa_resize_key = None
        if content:
            self._write_kitty_content(content)

    def _invalidate_chafa_resize_requests(self) -> None:
        self._chafa_resize_request_id += 1
        self._pending_chafa_resize_key = None
        if self._chafa_resize_timer is not None:
            self._chafa_resize_timer.stop()
            self._chafa_resize_timer = None

    @staticmethod
    def _should_clear_previous_kitty_preview(
        previous_state: ChildPaneViewState,
        next_state: ChildPaneViewState,
    ) -> bool:
        if not previous_state.is_preview or previous_state.preview_kind != "kitty":
            return False
        return (
            not next_state.is_preview
            or next_state.preview_kind != "kitty"
            or next_state.preview_path != previous_state.preview_path
            or next_state.preview_content != previous_state.preview_content
        )

    def _clear_kitty_content(self) -> None:
        self._write_terminal_content(_KITTY_DELETE_ALL_IMAGES)

    @staticmethod
    def _write_terminal_content(content: str) -> None:
        import os

        payload = content.encode("utf-8")
        try:
            tty_fd = os.open("/dev/tty", os.O_WRONLY)
            try:
                os.write(tty_fd, payload)
            finally:
                os.close(tty_fd)
        except OSError:
            import sys

            sys.stdout.buffer.write(payload)
            sys.stdout.buffer.flush()

    def scroll_preview(self, delta: int) -> None:
        """Scroll the preview content by *delta* lines (negative = up)."""
        if not self._state.is_preview:
            return
        try:
            scroll = self._preview_scroll_widget()
        except Exception:
            return
        scroll.scroll_relative(y=delta, animate=False)

    @staticmethod
    def _preview_identity(state: ChildPaneViewState) -> tuple[object, ...] | None:
        if not state.is_preview:
            return None
        return (
            state.preview_path,
            state.preview_title,
            state.preview_content,
            state.preview_kind,
            state.preview_message,
            state.preview_start_line,
            state.preview_highlight_line,
            state.view_kind,
            state.status,
            state.metadata,
        )

    @staticmethod
    def _render_signature(state: ChildPaneViewState) -> tuple[object, ...]:
        if state.is_preview:
            return (
                "preview",
                state.preview_path,
                state.preview_title,
                state.preview_content,
                state.preview_kind,
                state.preview_message,
                state.preview_start_line,
                state.preview_highlight_line,
                state.syntax_theme,
                state.view_kind,
                state.status,
                state.metadata,
            )
        return ("list", state.entries, state.scroll_entries)


def _render_kitty_preview_text(content: str) -> Text:
    """Kitty graphics protocol escape sequences cannot be split across
    individual grid cells by Rich/Textual.  The actual bytes are written
    to the terminal in :meth:`ChildPane._write_kitty_content` after
    each render cycle; this placeholder prevents the preview widget
    from showing anything else."""
    return Text("", no_wrap=True, overflow="ignore", end="")


def _render_image_preview_text(content: str) -> Text:
    text = Text(no_wrap=True, overflow="ignore", end="")
    current_style = Style()
    position = 0

    for match in _SGR_SEQUENCE_RE.finditer(content):
        if match.start() > position:
            text.append(content[position : match.start()], style=current_style)
        current_style = _apply_sgr_codes(current_style, match.group(1))
        position = match.end()

    if position < len(content):
        text.append(content[position:], style=current_style)

    return text


def _apply_sgr_codes(style: Style, raw_codes: str) -> Style:
    if not raw_codes:
        return Style()

    color = style.color
    bgcolor = style.bgcolor
    codes = [int(code) if code else 0 for code in raw_codes.split(";")]
    index = 0

    while index < len(codes):
        code = codes[index]
        if code == 0:
            color = None
            bgcolor = None
            index += 1
            continue
        if code == 39:
            color = None
            index += 1
            continue
        if code == 49:
            bgcolor = None
            index += 1
            continue
        if code == 38 and index + 4 < len(codes) and codes[index + 1] == 2:
            color = Color.from_rgb(codes[index + 2], codes[index + 3], codes[index + 4])
            index += 5
            continue
        if code == 48 and index + 4 < len(codes) and codes[index + 1] == 2:
            bgcolor = Color.from_rgb(codes[index + 2], codes[index + 3], codes[index + 4])
            index += 5
            continue
        index += 1

    return Style(color=color, bgcolor=bgcolor)
