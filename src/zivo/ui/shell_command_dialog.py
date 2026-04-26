"""One-line shell command input dialog widget."""

from rich.text import Text
from textual.containers import Container
from textual.widgets import Static

from zivo.models import ShellCommandDialogState


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
        yield Static("", id="shell-command-dialog-result")
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
            self.query_one("#shell-command-dialog-result", Static).update("")
            self.query_one("#shell-command-dialog-options", Static).update("")
            return

        self.query_one("#shell-command-dialog-title", Static).update(state.title)
        self.query_one("#shell-command-dialog-cwd", Static).update(f"Directory: {state.cwd}")
        self.query_one("#shell-command-dialog-input", Static).update(
            self._render_input(state.prompt, state.command)
        )
        self.query_one("#shell-command-dialog-result", Static).update(
            self._render_result(state.result)
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

    @staticmethod
    def _render_result(result) -> Text:
        """Render the shell command result (exit code, stdout, stderr)."""
        text = Text()
        if result is None:
            return text

        # 終了コードの表示
        exit_style = "green" if result.exit_code == 0 else "red"
        exit_label = (
            "Success"
            if result.exit_code == 0
            else f"Failed (exit code {result.exit_code})"
        )
        text.append(f"[{exit_label}] ", style=exit_style)
        text.append("\n")

        # 標準出力の表示
        if result.stdout:
            text.append("stdout:\n", style="bold")
            text.append(result.stdout, style="default")
            if not result.stdout.endswith("\n"):
                text.append("\n")

        # 標準エラーの表示
        if result.stderr:
            text.append("stderr:\n", style="bold red")
            text.append(result.stderr, style="red")
            if not result.stderr.endswith("\n"):
                text.append("\n")

        return text
