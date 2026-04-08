"""Command palette widget."""

from rich.text import Text
from textual.containers import Container
from textual.widgets import Static

from peneo.models import CommandPaletteViewState


class CommandPalette(Container):
    """Compact command palette shown above the help and status bars."""

    def __init__(
        self,
        state: CommandPaletteViewState | None,
        *,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes)
        self.state = state

    def compose(self):
        yield Static("Command Palette", id="command-palette-title")
        yield Static("", id="command-palette-query")
        yield Static("", id="command-palette-items")

    def on_mount(self) -> None:
        self.set_state(self.state)

    def set_state(self, state: CommandPaletteViewState | None) -> None:
        """Update palette content and visibility."""

        self.state = state
        self.display = state is not None
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
        query_text = Text()
        query_text.append("> ", style="bold")
        placeholder = (
            "type a filename or re:pattern"
            if state.title.startswith("Find File")
            else "type text or re:pattern"
            if state.title.startswith("Grep")
            else "type a path"
            if state.title.startswith("Directory History") or state.title.startswith("Go to path")
            else "type a command"
        )
        query_text.append(state.query or placeholder, style="bold" if state.query else "dim")
        query_widget.update(query_text)
        items_widget.update(self._render_items(state))

    @staticmethod
    def _render_items(state: CommandPaletteViewState) -> Text:
        if not state.items:
            return Text(state.empty_message, style="dim")

        rendered = Text()
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

            line.append("> " if item.selected else "  ", style=style)
            line.append(item.label, style=style)
            if item.shortcut:
                shortcut_style = "dim"
                if style:
                    shortcut_style = f"{style} dim"
                line.append(f" [{item.shortcut}]", style=shortcut_style)
            rendered.append_text(line)
            if index < len(state.items) - 1:
                rendered.append("\n")
        return rendered
