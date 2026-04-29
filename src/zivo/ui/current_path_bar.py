"""Current path widget shown at the top of the shell."""

from textual.widgets import Static

from zivo.windows_paths import display_path


class CurrentPathBar(Static):
    """Single-line widget that renders the active directory path."""

    def __init__(
        self,
        path: str,
        *,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(self.format_path(path), id=id, classes=classes)
        self.path = path

    @staticmethod
    def format_path(path: str) -> str:
        """Build the visible current-path line."""

        return f"Current Path: {display_path(path)}"

    def set_path(self, path: str) -> None:
        """Update the rendered path without remounting the widget."""

        if path == self.path:
            return

        self.path = path
        self.update(self.format_path(path))
