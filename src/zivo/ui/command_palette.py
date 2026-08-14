"""Command palette widget."""

import re

from rich.cells import cell_len
from rich.style import Style
from rich.text import Text
from textual import events
from textual.containers import Container, VerticalScroll
from textual.events import Click
from textual.widgets import Static

from zivo.models import (
    CommandPaletteInputFieldViewState,
    CommandPaletteItemViewState,
    CommandPaletteViewState,
)
from zivo.state.actions import (
    BeginReplaceFromSearchResults,
    MoveCommandPaletteCursor,
    SubmitCommandPalette,
)
from zivo.ui.panes import truncate_middle


class _CommandPaletteItemsScroll(VerticalScroll):
    """Expand projected result rows before the first wheel movement."""

    def _owner_palette(self) -> "CommandPalette | None":
        for ancestor in self.ancestors:
            if isinstance(ancestor, CommandPalette):
                return ancestor
        return None

    def _on_mouse_scroll_down(self, event: events.MouseScrollDown) -> None:
        owner = self._owner_palette()
        if owner is not None and owner._prepare_result_scroll():
            event.stop()
            self.call_after_refresh(
                lambda: owner._scroll_after_expand(self, down=True)
            )
            return
        super()._on_mouse_scroll_down(event)

    def _on_mouse_scroll_up(self, event: events.MouseScrollUp) -> None:
        owner = self._owner_palette()
        if owner is not None and owner._prepare_result_scroll():
            event.stop()
            self.call_after_refresh(
                lambda: owner._scroll_after_expand(self, down=False)
            )
            return
        super()._on_mouse_scroll_up(event)


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
        self._scroll_items: tuple[CommandPaletteItemViewState, ...] | None = None
        self._scroll_expanded = False
        self._scroll_key: str | None = None
        self._last_cursor_index: int | None = None
        self._pending_scroll_anchor = 0

    def compose(self):
        yield Static("Command Palette", id="command-palette-title")
        yield Static("", id="command-palette-query")
        yield Static("", id="command-palette-context")
        yield _CommandPaletteItemsScroll(
            Static("", id="command-palette-items"),
            id="command-palette-items-scroll",
        )
        yield Static("", id="command-palette-footer")

    def on_mount(self) -> None:
        self.set_state(self.state)

    async def on_click(self, event: Click) -> None:
        if self.state is None:
            return

        meta = event.style.meta
        if meta.get("palette_action") == "replace_results":
            event.stop()
            await self.app.dispatch_actions((BeginReplaceFromSearchResults(),))
            return
        item_index = meta.get("palette_item_index")
        if not isinstance(item_index, int):
            return

        event.stop()

        current_cursor = self._state_cursor_index()

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
            self._scroll_items = None
            self._scroll_expanded = False
            self._scroll_key = None
            self._last_cursor_index = None
        title_widget = self.query_one("#command-palette-title", Static)
        query_widget = self.query_one("#command-palette-query", Static)
        context_widget = self.query_one("#command-palette-context", Static)
        items_widget = self.query_one("#command-palette-items", Static)
        footer_widget = self.query_one("#command-palette-footer", Static)

        if state is None:
            self.remove_class("-expanded")
            self.remove_class("-result-list")
            title_widget.update("Command Palette")
            query_widget.update("")
            context_widget.display = False
            context_widget.update("")
            items_widget.update("")
            footer_widget.display = False
            footer_widget.update("")
            return

        context_changed = state.scroll_key != self._scroll_key
        if context_changed:
            self._scroll_expanded = False
        self._scroll_items = state.scroll_items
        self._scroll_key = state.scroll_key
        cursor_index = self._state_cursor_index(state)
        cursor_changed = cursor_index != self._last_cursor_index
        self._last_cursor_index = cursor_index
        self.set_class(state.has_more_items, "-expanded")
        self.set_class(state.scroll_items is not None, "-result-list")
        title_widget.update(state.title)
        is_search_results = state.title.startswith("Find") or state.title.startswith("Grep")
        footer_widget.display = bool(state.footer_message) or (
            is_search_results and bool(state.items)
        )
        query_width = self._resolve_render_width(query_widget)
        items_width = self._resolve_render_width(items_widget)
        if state.input_fields:
            query_widget.update(self._render_input_fields(state.input_fields, query_width))
        else:
            query_widget.update(self._render_query_line(state, query_width))
        context_lines = [*state.context_lines]
        if state.category_hint:
            context_lines.append(state.category_hint)
        context_widget.display = bool(context_lines)
        context_widget.update(
            Text("\n".join(context_lines), style="dim", no_wrap=True, overflow="ellipsis")
            if context_lines
            else ""
        )
        rendered_items, index_offset = self._rendered_items(state)
        items_widget.update(self._render_items(state, items_width, rendered_items, index_offset))
        footer_text = Text()
        if is_search_results and state.items:
            footer_text.append(
                "Ctrl+r Replace results",
                style=Style(meta={"palette_action": "replace_results"}),
            )
            if state.footer_message:
                footer_text.append(" · ")
        if state.footer_message:
            footer_text.append(
                truncate_middle(
                    state.footer_message,
                    self._resolve_render_width(footer_widget),
                ),
                style="yellow",
            )
        footer_widget.update(footer_text if len(footer_text) else "")
        if context_changed or cursor_changed:
            self.call_after_refresh(self._scroll_selected_item)

    def _prepare_result_scroll(self) -> bool:
        """Expand a bounded search/replace result projection for mouse scrolling."""

        if self._scroll_expanded or self._scroll_items is None:
            return False
        state = self.state
        if state is None:
            return False
        _, previous_index_offset = self._rendered_items(state)
        self._scroll_expanded = True
        items_widget = self.query_one("#command-palette-items", Static)
        rendered_items, index_offset = self._rendered_items(state)
        items_widget.update(
            self._render_items(
                state,
                self._resolve_render_width(items_widget),
                rendered_items,
                index_offset,
            )
        )
        self._pending_scroll_anchor = previous_index_offset
        return True

    def _scroll_after_expand(
        self,
        scroll_widget: VerticalScroll,
        *,
        down: bool,
    ) -> None:
        """Restore the previous result window before applying wheel movement."""

        scroll_widget.scroll_to(
            y=self._pending_scroll_anchor,
            animate=False,
            force=True,
            immediate=True,
        )
        if down:
            scroll_widget.scroll_down(animate=False, immediate=True)
        else:
            scroll_widget.scroll_up(animate=False, immediate=True)

    def _rendered_items(
        self,
        state: CommandPaletteViewState,
    ) -> tuple[tuple[CommandPaletteItemViewState, ...], int]:
        if self._scroll_expanded and self._scroll_items is not None:
            return self._scroll_items, 0
        return state.items, self._result_index_offset(state.title)

    def _state_cursor_index(self, state: CommandPaletteViewState | None = None) -> int:
        current_state = state or self.state
        if current_state is None:
            return 0
        if current_state.cursor_index is not None:
            return current_state.cursor_index
        for index, item in enumerate(current_state.items):
            if item.selected:
                return index + self._result_index_offset(current_state.title)
        return 0

    @staticmethod
    def _result_index_offset(title: str) -> int:
        match = re.search(r"\((\d+)-\d+ / \d+\)$", title)
        return int(match.group(1)) - 1 if match else 0

    def _scroll_selected_item(self) -> None:
        """Keep the selected row visible when cursor navigation crosses the fold."""

        if self.state is None:
            return
        scroll_widget = self.query_one("#command-palette-items-scroll", VerticalScroll)
        rendered_items, index_offset = self._rendered_items(self.state)
        selected_index = self._state_cursor_index()
        local_selected_index = selected_index - index_offset
        if local_selected_index < 0 or local_selected_index >= len(rendered_items):
            return
        show_sections = (
            self.state.title.startswith("Command Palette") and not self.state.query.strip()
        )
        selected_line = local_selected_index
        if show_sections:
            current_section: str | None = None
            for item in rendered_items[: local_selected_index + 1]:
                if item.category != current_section:
                    if current_section is not None:
                        selected_line += 1
                    selected_line += 1
                    current_section = item.category
        viewport_height = scroll_widget.content_region.height or scroll_widget.size.height
        if viewport_height <= 0:
            return
        current_y = int(scroll_widget.scroll_y)
        visible_bottom = current_y + viewport_height - 1
        if current_y <= selected_line <= visible_bottom:
            return
        target_y = (
            selected_line
            if selected_line < current_y
            else selected_line - viewport_height + 1
        )
        target_y = max(0, target_y)
        scroll_widget.scroll_to(
            y=target_y,
            animate=False,
            force=True,
            immediate=True,
        )
        scroll_widget.refresh()

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
            state.title.startswith("Go")
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
        if state.title.startswith("Go") and not state.query:
            placeholder = "path or @bookmark @history @tab @home"
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
    def _render_items(
        cls,
        state: CommandPaletteViewState,
        render_width: int,
        items: tuple[CommandPaletteItemViewState, ...] | None = None,
        index_offset: int = 0,
    ) -> Text:
        rendered_items = items if items is not None else state.items
        if not rendered_items:
            return Text(state.empty_message, style="dim", no_wrap=True, overflow="ellipsis")

        rendered = Text(no_wrap=True, overflow="ellipsis")
        show_sections = state.title.startswith("Command Palette") and not state.query.strip()
        current_section: str | None = None
        for local_index, item in enumerate(rendered_items):
            index = local_index + index_offset
            section = item.category
            if show_sections and section != current_section:
                if len(rendered):
                    rendered.append("\n")
                rendered.append(section, style="bold dim")
                rendered.append("\n")
                current_section = section
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
            if local_index < len(rendered_items) - 1:
                rendered.append("\n")
        return rendered
