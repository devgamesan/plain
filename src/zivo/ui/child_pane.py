"""Child pane widget that toggles between list and preview modes."""

import re

from rich.color import Color
from rich.style import Style
from rich.syntax import Syntax
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.css.query import NoMatches
from textual.message import Message
from textual.widgets import Label, Static

from zivo.models.shell_data import ChildPaneViewState

from .pane_rendering import (
    FILE_TYPE_COMPONENT_CLASSES,
    _guess_preview_lexer,
    _render_file_entries,
    _resolve_component_styles,
)
from .side_pane import SidePane

_SGR_SEQUENCE_RE = re.compile(r"\x1b\[([0-9;]*)m")


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

    def __init__(
        self,
        state: ChildPaneViewState,
        *,
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
        self._chafa_cached_content: str | None = None
        self._last_chafa_width: int = 0

    @property
    def list_view_id(self) -> str | None:
        return f"{self.id}-list" if self.id else None

    @property
    def preview_id(self) -> str | None:
        return f"{self.id}-preview" if self.id else None

    @property
    def preview_scroll_id(self) -> str | None:
        return f"{self.id}-preview-scroll" if self.id else None

    @property
    def permissions_id(self) -> str | None:
        return f"{self.id}-permissions" if self.id else None

    def compose(self) -> ComposeResult:
        yield Label(self._state.title, classes="pane-title")
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
        yield list_content
        yield preview_scroll
        permissions = Static(
            self._state.permissions_label,
            id=self.permissions_id,
            classes="pane-permissions",
        )
        permissions.can_focus = False
        yield permissions

    def on_mount(self) -> None:
        self._ft_styles = _resolve_component_styles(self)
        self.call_after_refresh(self._refresh_rendered_content)

    def on_resize(self, _event: events.Resize) -> None:
        self._refresh_rendered_content()

    def on_click(self, event: events.Click) -> None:
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
        new_path = str(path) if path is not None else None
        if new_path != self._hovered_path:
            self._hovered_path = new_path
            self._refresh_rendered_content(force=True)

    def on_leave(self, _event: events.Leave) -> None:
        if self._state.is_preview:
            return
        if self._hovered_path is not None:
            self._hovered_path = None
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
        self._state = state
        if state.title != previous_state.title:
            self.query_one(Label).update(state.title)
        list_widget = self._list_widget()
        scroll_widget = self._preview_scroll_widget()
        if mode_changed:
            list_widget.display = not state.is_preview
            scroll_widget.display = state.is_preview
        if state.permissions_label != previous_state.permissions_label:
            self._permissions_widget().update(state.permissions_label)
        if render_signature_changed or mode_changed:
            rendered = self._refresh_rendered_content(force=True)
            if not rendered:
                self.call_after_refresh(self._refresh_rendered_content)
        if preview_identity_changed:
            object.__setattr__(self, "_chafa_cached_content", None)
            object.__setattr__(self, "_last_chafa_width", 0)
            if state.is_preview:
                self.call_after_refresh(lambda: scroll_widget.scroll_home(animate=False))

    def _refresh_rendered_content(self, *, force: bool = False) -> bool:
        render_signature = self._render_signature(self._state)
        try:
            if self._state.is_preview:
                widget = self._preview_widget()
                render_width = max(0, widget.size.width - self.PREVIEW_HORIZONTAL_PADDING)
                if render_width <= 0:
                    return False
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
                    try:
                        from pathlib import Path as FsPath

                        from zivo.services.previews.core import (
                            ChafaImagePreviewLoader,
                        )

                        loader = ChafaImagePreviewLoader()
                        result = loader.load_preview(
                            FsPath(self._state.preview_path),
                            preview_columns=render_width,
                            image_preview_format="symbols",
                        )
                        if result and result.content:
                            object.__setattr__(
                                self, "_chafa_cached_content", result.content
                            )
                        object.__setattr__(self, "_last_chafa_width", render_width)
                    except Exception:
                        pass

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
        widget.update(
            _render_file_entries(
                self._state.entries,
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

    def _list_widget(self) -> Static:
        return self.query_one(f"#{self.list_view_id}", Static)

    def _preview_widget(self) -> Static:
        return self.query_one(f"#{self.preview_id}", Static)

    def _preview_scroll_widget(self) -> VerticalScroll:
        return self.query_one(f"#{self.preview_scroll_id}", VerticalScroll)

    def _permissions_widget(self) -> Static:
        return self.query_one(f"#{self.permissions_id}", Static)

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
            import os
            from pathlib import Path as FsPath

            from zivo.services.previews.core import (
                ChafaImagePreviewLoader,
                resolve_image_preview_format,
            )

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

            if pane_width != last_width and path:
                loader = ChafaImagePreviewLoader()
                result = loader.load_preview(
                    FsPath(path),
                    preview_columns=pane_width,
                    image_preview_format="kitty",
                )
                if result and result.content:
                    content = result.content
                    object.__setattr__(self, "_kitty_cached", content)
                object.__setattr__(self, "_last_kitty_width", pane_width)
            else:
                cached = getattr(self, "_kitty_cached", None)
                if cached is not None:
                    content = cached

            if not content:
                return

            row = region.y + 1
            col = region.x + 1
            write = f"\033_Ga=d,d=A\033\\\033[{row};{col}H{content}"
            payload = write.encode("utf-8")
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
        except Exception:
            pass

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
            )
        return ("list", state.entries)


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
