"""One-line shell command input dialog widget."""

from rich.text import Text
from textual.containers import Container
from textual.widgets import Static

from peneo.models import ShellCommandDialogState


class ShellCommandDialog(Container):
    """Simple overlay used to collect a shell command."""

    def __init__(
        self,
        state: ShellCommandDialogState | None,
        *,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes)
        self.state = state

    def compose(self):
        yield Static("", id="shell-command-dialog-title")
        yield Static("", id="shell-command-dialog-cwd")
        yield Static("", id="shell-command-dialog-input")
        yield Static("", id="shell-command-dialog-options")

    def on_mount(self) -> None:
        self.set_state(self.state)

    def set_state(self, state: ShellCommandDialogState | None) -> None:
        """Update dialog content and visibility."""

        self.state = state
        self.display = state is not None
        if state is None:
            self.query_one("#shell-command-dialog-title", Static).update("")
            self.query_one("#shell-command-dialog-cwd", Static).update("")
            self.query_one("#shell-command-dialog-input", Static).update("")
            self.query_one("#shell-command-dialog-options", Static).update("")
            return

        self.query_one("#shell-command-dialog-title", Static).update(state.title)
        self.query_one("#shell-command-dialog-cwd", Static).update(f"Directory: {state.cwd}")
        self.query_one("#shell-command-dialog-input", Static).update(
            self._render_input(state.prompt, state.command)
        )
        self.query_one("#shell-command-dialog-options", Static).update(
            f"Actions: {' | '.join(state.options)}"
        )

    @staticmethod
    def _render_input(prompt: str, command: str) -> Text:
        text = Text()
        text.append(prompt, style="bold")
        text.append(command or "_", style="underline")
        return text
