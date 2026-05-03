"""Command palette widget."""

from rich.cells import cell_len
from rich.style import Style
from rich.text import Text
from textual.containers import Container
from textual.events import Click
from textual.widgets import Static

from zivo.models import CommandPaletteInputFieldViewState, CommandPaletteViewState
from zivo.state.actions import MoveCommandPaletteCursor, SubmitCommandPalette
from zivo.ui.panes import truncate_middle


class CommandPalette(Container):
    """Compact command palette shown above the help and status bars."""

    _DEFAULT_RENDER_WIDTH = 120

    def __init__(
        self,
        state: CommandPaletteViewState | None,
        *,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes)
        self.state = state
        self._last_clicked_index: int = -1

    def compose(self):
        yield Static("Command Palette", id="command-palette-title")
        yield Static("", id="command-palette-query")
        yield Static("", id="command-palette-items")

    def on_mount(self) -> None:
        self.set_state(self.state)

    async def on_click(self, event: Click) -> None:
        if self.state is None:
            return

        meta = event.style.meta
        item_index = meta.get("palette_item_index")
        if not isinstance(item_index, int):
            return

        event.stop()

        current_cursor = 0
        for i, item in enumerate(self.state.items):
            if item.selected:
                current_cursor = i
                break

        delta = item_index - current_cursor

        actions: list = [MoveCommandPaletteCursor(delta)]
        double_click = item_index == self._last_clicked_index
        self._last_clicked_index = item_index
        if double_click:
            actions.append(SubmitCommandPalette())

        await self.app.dispatch_actions(tuple(actions))

    def set_state(self, state: CommandPaletteViewState | None) -> None:
        """Update palette content and visibility."""

        self.state = state
        self.display = state is not None
        if state is None:
            self._last_clicked_index = -1
        title_widget = self.query_one("#command-palette-title", Static)
        query_widget = self.query_one("#command-palette-query", Static)
        items_widget = self.query_one("#command-palette-items", Static)

        if state is None:
            self.remove_class("-expanded")
            title_widget.update("Command Palette")
            query_widget.update("")
            items_widget.update("")
            return

        self.set_class(state.has_more_items, "-expanded")
        title_widget.update(state.title)
        query_width = self._resolve_render_width(query_widget)
        items_width = self._resolve_render_width(items_widget)
        if state.input_fields:
            query_widget.update(self._render_input_fields(state.input_fields, query_width))
        else:
            query_widget.update(self._render_query_line(state, query_width))
        items_widget.update(self._render_items(state, items_width))

    @staticmethod
    def _resolve_render_width(widget: Static) -> int:
        for width in (widget.content_region.width, widget.size.width, widget.region.width):
            if width > 0:
                return width
        return CommandPalette._DEFAULT_RENDER_WIDTH

    @classmethod
    def _render_query_line(cls, state: CommandPaletteViewState, render_width: int) -> Text:
        query_text = Text()
        query_text.append("> ", style="bold")
        is_path_source = (
            state.title.startswith("Directory History")
            or state.title.startswith("Go to path")
            or state.title.startswith("Bookmarks")
        )
        placeholder = (
            "type a filename or re:pattern"
            if state.title.startswith("Find File")
            else "type text or re:pattern"
            if state.title.startswith("Grep")
            else "type text or re:pattern"
            if state.title.startswith("Replace Text")
            else "type a path"
            if is_path_source
            else "type a command"
        )
        available_width = max(1, render_width - cell_len("> "))
        value = truncate_middle(state.query or placeholder, available_width)
        query_text.no_wrap = True
        query_text.overflow = "ellipsis"
        query_text.append(value, style="bold" if state.query else "dim")
        return query_text

    @classmethod
    def _render_input_fields(
        cls,
        fields: tuple[CommandPaletteInputFieldViewState, ...],
        render_width: int,
    ) -> Text:
        rendered = Text(no_wrap=True, overflow="ellipsis")
        for index, field in enumerate(fields):
            label_style = "reverse bold" if field.active else "bold"
            value_style = "bold" if field.active and field.value else ""
            placeholder_style = "dim"
            prefix = f"{field.label:>8}: "
            rendered.append(prefix, style=label_style)
            available_width = max(1, render_width - cell_len(prefix))
            if field.value:
                rendered.append(truncate_middle(field.value, available_width), style=value_style)
            else:
                rendered.append(
                    truncate_middle(field.placeholder, available_width),
                    style=placeholder_style,
                )
            if index < len(fields) - 1:
                rendered.append("\n")
        return rendered

    @classmethod
    def _render_items(cls, state: CommandPaletteViewState, render_width: int) -> Text:
        if not state.items:
            return Text(state.empty_message, style="dim", no_wrap=True, overflow="ellipsis")

        rendered = Text(no_wrap=True, overflow="ellipsis")
        for index, item in enumerate(state.items):
            line = Text()
            if item.selected and item.enabled:
                style = "reverse"
            elif item.selected and not item.enabled:
                style = "reverse dim"
            elif not item.enabled:
                style = "dim"
            else:
                style = ""

            meta = {"palette_item_index": index}
            combined = Style(meta=meta)
            if style:
                combined += Style.parse(style)

            prefix = "> " if item.selected else "  "
            shortcut_suffix = f" [{item.shortcut}]" if item.shortcut else ""
            line.append(prefix, style=combined)
            available_width = max(
                1,
                render_width - cell_len(prefix) - cell_len(shortcut_suffix),
            )
            label = truncate_middle(item.label, available_width)
            line.append(label, style=combined)
            if item.shortcut:
                combined_shortcut = Style(meta=meta)
                combined_shortcut += Style.parse(f"{style} dim" if style else "dim")
                line.append(shortcut_suffix, style=combined_shortcut)
            rendered.append_text(line)
            if index < len(state.items) - 1:
                rendered.append("\n")
        return rendered
