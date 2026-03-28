"""Split-terminal widget."""

import re

import pyte
from pyte.screens import Char, Screen
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.geometry import Size
from textual.timer import Timer
from textual.widgets import Static

from peneo.models import SplitTerminalViewState


class SplitTerminalPane(Static):
    """Embedded split-terminal output pane."""

    DEFAULT_COLUMNS = 80
    DEFAULT_ROWS = 8
    RENDER_COALESCE_SECONDS = 1 / 30

    DEFAULT_STATE = SplitTerminalViewState(
        visible=False,
        title="Split Terminal",
        status="closed",
        body="",
        focused=False,
    )

    def __init__(
        self,
        state: SplitTerminalViewState,
        *,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes)
        self.can_focus = True
        self.state = state
        self._screen: Screen | None = None
        self._stream: pyte.Stream | None = None
        self._has_terminal_output = False
        self._pending_escape_sequence = ""
        self._screen_columns = self.DEFAULT_COLUMNS
        self._screen_rows = self.DEFAULT_ROWS
        self._render_timer: Timer | None = None
        self._render_pending = False

    def compose(self) -> ComposeResult:
        yield Static("", id="split-terminal-title")
        yield Static("", id="split-terminal-status")
        with VerticalScroll(id="split-terminal-scroll"):
            yield Static("", id="split-terminal-body")

    def on_mount(self) -> None:
        self.set_state(self.state)

    def on_unmount(self) -> None:
        self._cancel_pending_render()

    def on_resize(self, _event: events.Resize) -> None:
        if not self.state.visible:
            return
        columns, rows = self.terminal_dimensions()
        if self._screen is not None:
            self._screen.resize(lines=rows, columns=columns)
            self._screen_columns = columns
            self._screen_rows = rows
        self._render_body()

    def terminal_dimensions(self) -> tuple[int, int]:
        """Return the PTY size that best matches the visible body area."""

        try:
            scroll = self.query_one("#split-terminal-scroll", VerticalScroll)
        except Exception:
            return (self.DEFAULT_COLUMNS, self.DEFAULT_ROWS)

        size: Size = scroll.content_region.size
        columns = size.width or scroll.size.width or self.DEFAULT_COLUMNS
        rows = size.height or scroll.size.height or self.DEFAULT_ROWS
        return (max(20, columns), max(2, rows))

    def set_state(self, state: SplitTerminalViewState) -> None:
        """Update visibility and rendered terminal content."""

        was_visible = self.state.visible
        self.state = state
        self.display = state.visible
        self.set_class(state.visible, "-visible")
        self.set_class(state.focused, "-focused")

        title = self.query_one("#split-terminal-title", Static)
        status = self.query_one("#split-terminal-status", Static)

        title.update(state.title)
        status.update(f"Status: {state.status}")
        if was_visible and not state.visible:
            self._reset_terminal_screen()
        self._render_body()

    def append_output(self, data: str) -> None:
        """Feed raw PTY output into the emulator and redraw the pane."""

        if not self.state.visible or not data:
            return

        columns, rows = self.terminal_dimensions()
        self._ensure_terminal_screen(columns=columns, rows=rows)
        safe_data = self._take_complete_terminal_data(data)
        sanitized = _sanitize_terminal_output(safe_data)
        if sanitized and self._stream is not None:
            try:
                self._stream.feed(sanitized)
            except Exception:
                # Ignore unsupported terminal queries instead of crashing the app.
                pass
            else:
                self._has_terminal_output = True
                self._schedule_render()

    def _render_body(self) -> None:
        self._cancel_pending_render()
        body = self.query_one("#split-terminal-body", Static)
        rendered = Text("")
        if self.state.visible:
            if self._has_terminal_output and self._screen is not None:
                rendered = _screen_to_text(self._screen, focused=self.state.focused)
            else:
                rendered = Text(self.state.body)
        else:
            self._reset_terminal_screen()
        body.update(rendered)

    def _schedule_render(self) -> None:
        if self._render_pending:
            return
        self._render_pending = True
        self._render_timer = self.set_timer(
            self.RENDER_COALESCE_SECONDS,
            self._flush_render,
            name="split-terminal-render",
        )

    def _flush_render(self) -> None:
        self._render_timer = None
        self._render_pending = False
        self._render_body()

    def _cancel_pending_render(self) -> None:
        if self._render_timer is not None:
            self._render_timer.stop()
            self._render_timer = None
        self._render_pending = False

    def _ensure_terminal_screen(self, *, columns: int, rows: int) -> None:
        if self._screen is None or self._stream is None:
            self._reset_terminal_screen(columns=columns, rows=rows)
            return
        if columns != self._screen_columns or rows != self._screen_rows:
            self._screen.resize(lines=rows, columns=columns)
            self._screen_columns = columns
            self._screen_rows = rows

    def _reset_terminal_screen(
        self,
        *,
        columns: int | None = None,
        rows: int | None = None,
    ) -> None:
        self._screen_columns = columns or self.DEFAULT_COLUMNS
        self._screen_rows = rows or self.DEFAULT_ROWS
        self._screen = Screen(self._screen_columns, self._screen_rows)
        self._stream = pyte.Stream(self._screen, strict=False)
        self._has_terminal_output = False
        self._pending_escape_sequence = ""

    def _take_complete_terminal_data(self, data: str) -> str:
        combined = self._pending_escape_sequence + data
        complete, pending = _split_complete_terminal_data(combined)
        self._pending_escape_sequence = pending
        return complete


_DEFAULT_CHAR = Char(" ")
_DCS_SEQUENCE_RE = re.compile(r"\x1bP.*?(?:\x1b\\|\x9c)", re.DOTALL)
_OSC_SEQUENCE_RE = re.compile(r"\x1b\].*?(?:\x07|\x1b\\|\x9c)", re.DOTALL)
_PRIVATE_SGR_RE = re.compile(r"\x1b\[[?>][0-9;]*m")
_INCOMPLETE_CSI_RE = re.compile(r"(\x1b\[[0-9:;<=>?]*[ -/]*)$")
_TERMINAL_COLOR_MAP = {
    "black": "black",
    "red": "red",
    "green": "green",
    "brown": "yellow",
    "blue": "blue",
    "magenta": "magenta",
    "cyan": "cyan",
    "white": "white",
    "brightblack": "bright_black",
    "brightred": "bright_red",
    "brightgreen": "bright_green",
    "brightyellow": "bright_yellow",
    "brightblue": "bright_blue",
    "brightmagenta": "bright_magenta",
    "brightcyan": "bright_cyan",
    "brightwhite": "bright_white",
}


def _sanitize_terminal_output(data: str) -> str:
    data = _DCS_SEQUENCE_RE.sub("", data)
    data = _OSC_SEQUENCE_RE.sub("", data)
    return _PRIVATE_SGR_RE.sub("", data)


def _split_complete_terminal_data(data: str) -> tuple[str, str]:
    if data.endswith("\x1b"):
        return (data[:-1], "\x1b")
    match = _INCOMPLETE_CSI_RE.search(data)
    if match is None:
        return (data, "")
    pending = match.group(1)
    return (data[: -len(pending)], pending)


def _screen_to_text(screen: Screen, *, focused: bool) -> Text:
    text = Text()
    for row in range(screen.lines):
        if row:
            text.append("\n")
        text.append_text(_screen_row_text(screen, row, focused=focused))
    return text


def _screen_row_text(screen: Screen, row: int, *, focused: bool) -> Text:
    row_buffer = screen.buffer.get(row, {})
    cursor_x = -1
    if focused and not screen.cursor.hidden and row == screen.cursor.y:
        cursor_x = screen.cursor.x
    visible_columns = [index for index, char in row_buffer.items() if char.data != " "]
    if cursor_x >= 0:
        visible_columns.append(cursor_x)
    max_column = max(visible_columns, default=-1)

    row_text = Text()
    for column in range(max_column + 1):
        char = row_buffer.get(column, _DEFAULT_CHAR)
        style = _terminal_style(char, is_cursor=column == cursor_x)
        row_text.append(char.data or " ", style=style)
    return row_text


def _terminal_style(char: Char, *, is_cursor: bool) -> str | None:
    fg = char.bg if char.reverse else char.fg
    bg = char.fg if char.reverse else char.bg
    tokens: list[str] = []
    color = _TERMINAL_COLOR_MAP.get(fg)
    if color is not None:
        tokens.append(color)
    background = _TERMINAL_COLOR_MAP.get(bg)
    if background is not None:
        tokens.append(f"on {background}")
    if char.bold:
        tokens.append("bold")
    if char.italics:
        tokens.append("italic")
    if char.underscore:
        tokens.append("underline")
    if char.strikethrough:
        tokens.append("strike")
    if is_cursor:
        tokens.append("reverse")
    return " ".join(tokens) or None
