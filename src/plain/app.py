"""Application assembly for Plain."""

from textual.app import App, ComposeResult
from textual.containers import Horizontal

from plain.models import build_dummy_shell_data
from plain.ui import MainPane, SidePane, StatusBar


class PlainApp(App[None]):
    """Minimal three-pane shell used as the initial UI skeleton."""

    TITLE = "Plain"
    SUB_TITLE = "Three-pane shell"
    CSS = """
    Screen {
        layout: vertical;
    }

    #body {
        height: 1fr;
        layout: horizontal;
    }

    .pane {
        height: 1fr;
        min-width: 24;
        border: round $surface;
        background: $boost;
    }

    .side-pane {
        width: 1fr;
    }

    .main-pane {
        width: 2fr;
        min-width: 40;
    }

    .pane-title {
        height: 1;
        padding: 0 1;
        background: $surface;
        color: $text-muted;
        text-style: bold;
    }

    .pane-list,
    .pane-table {
        height: 1fr;
    }

    .pane-entry {
        padding: 0 1;
    }

    #status-bar {
        height: 1;
        padding: 0 1;
        background: $surface;
        color: $text;
    }
    """

    def compose(self) -> ComposeResult:
        shell = build_dummy_shell_data()
        yield Horizontal(
            SidePane(
                "親ディレクトリ",
                shell.parent_entries,
                id="parent-pane",
                classes="pane side-pane",
            ),
            MainPane(
                "カレントディレクトリ",
                shell.current_entries,
                id="current-pane",
                classes="pane main-pane",
            ),
            SidePane(
                "子ディレクトリ",
                shell.child_entries,
                id="child-pane",
                classes="pane side-pane",
            ),
            id="body",
        )
        yield StatusBar(shell.status, id="status-bar")


def create_app() -> PlainApp:
    """Create the application instance."""
    return PlainApp()
