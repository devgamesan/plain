"""Application assembly for Plain."""

from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Footer, Header, Static


class PlainApp(App[None]):
    """Minimal placeholder app used as the project bootstrap."""

    TITLE = "Plain"
    SUB_TITLE = "Textual bootstrap"

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Static("Plain bootstrap is ready.", id="message"),
            Static("Next issues will add panes, state, and effects.", id="next-steps"),
            id="root",
        )
        yield Footer()


def create_app() -> PlainApp:
    """Create the application instance."""
    return PlainApp()

