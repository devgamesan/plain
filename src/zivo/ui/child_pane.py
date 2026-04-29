"""Child pane widget that toggles between list and preview modes."""

from rich.style import Style
from rich.syntax import Syntax
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.css.query import NoMatches
from textual.widgets import Label, Static

from zivo.models.shell_data import ChildPaneViewState

from .pane_rendering import (
    FILE_TYPE_COMPONENT_CLASSES,
    _guess_preview_lexer,
    _render_file_entries,
    _resolve_component_styles,
)
from .side_pane import SidePane


class ChildPane(Vertical):
    """Right-side pane that switches between entries and text preview."""

    COMPONENT_CLASSES = FILE_TYPE_COMPONENT_CLASSES
    PREVIEW_HORIZONTAL_PADDING = 2
    SELECTED_DIRECTORY_STYLE = "ft-directory-sel"
    SELECTED_CUT_STYLE = "ft-cut"

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
        preview_scroll.can_focus = False
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
        if preview_identity_changed and state.is_preview:
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
                widget.update(self._render_preview(self._state, render_width))
                self._last_render_width = render_width
                self._last_render_signature = render_signature
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
    def _render_preview(state: ChildPaneViewState, render_width: int):
        if state.preview_message is not None:
            return Text(state.preview_message, style="italic dim")

        if state.preview_content is None:
            return Text()

        if state.preview_kind == "image":
            return Text.from_ansi(
                state.preview_content,
                no_wrap=True,
                overflow="ignore",
                end="",
            )

        lexer = "text"
        if state.preview_path is not None:
            lexer = _guess_preview_lexer(state.preview_path)

        return Syntax(
            state.preview_content,
            lexer=lexer,
            theme=state.syntax_theme,
            word_wrap=False,
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
