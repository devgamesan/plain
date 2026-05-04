"""About dialog widget."""

from rich.text import Text
from textual.containers import Container
from textual.widgets import Static

from zivo.models import AboutDialogState


class AboutDialog(Container):
    """Simple overlay that shows application information."""

    def __init__(
        self,
        state: AboutDialogState | None,
        *,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes)
        self.state = state

    def compose(self):
        yield Static("", id="about-dialog-title")
        yield Static("", id="about-dialog-lines")
        yield Static("", id="about-dialog-options")

    def on_mount(self) -> None:
        self.set_state(self.state)

    def set_state(self, state: AboutDialogState | None) -> None:
        """Update dialog content and visibility."""

        self.state = state
        self.display = state is not None
        if state is None:
            self.query_one("#about-dialog-title", Static).update("")
            self.query_one("#about-dialog-lines", Static).update("")
            self.query_one("#about-dialog-options", Static).update("")
            return

        self.query_one("#about-dialog-title", Static).update(state.title)
        self.query_one("#about-dialog-lines", Static).update(self._render_lines(state.lines))
        self.query_one("#about-dialog-options", Static).update(
            f"Actions: {' | '.join(state.options)}"
        )

    @staticmethod
    def _render_lines(lines: tuple[str, ...]) -> Text:
        rendered = Text()
        for index, line in enumerate(lines):
            rendered.append(line)
            if index < len(lines) - 1:
                rendered.append("\n")
        return rendered
