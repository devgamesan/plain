"""Reusable widgets for the initial three-pane shell."""

from collections.abc import Sequence

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import DataTable, Label, ListItem, ListView

from plain.models.shell_data import PaneEntry


class SidePane(Vertical):
    """Lightweight pane used for parent and child directory listings."""

    def __init__(
        self,
        title: str,
        entries: Sequence[PaneEntry],
        *,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes)
        self._title = title
        self._entries = tuple(entries)

    @property
    def list_view_id(self) -> str | None:
        """Return the derived list view identifier for tests and styling."""
        return f"{self.id}-list" if self.id else None

    def compose(self) -> ComposeResult:
        yield Label(self._title, classes="pane-title")
        list_view = ListView(
            *self._build_items(self._entries),
            id=self.list_view_id,
            classes="pane-list",
        )
        list_view.can_focus = False
        yield list_view

    async def set_entries(self, entries: Sequence[PaneEntry]) -> None:
        """Replace the rendered entries without remounting the pane."""

        next_entries = tuple(entries)
        if next_entries == self._entries:
            return

        self._entries = next_entries
        list_view = self.query_one(ListView)
        await list_view.clear()
        items = self._build_items(self._entries)
        if items:
            await list_view.extend(items)

    @staticmethod
    def _build_items(entries: Sequence[PaneEntry]) -> tuple[ListItem, ...]:
        return tuple(
            ListItem(Label(entry.name, classes="pane-entry-label"), classes="pane-entry")
            for entry in entries
        )


class MainPane(Vertical):
    """Center pane with detailed columns for the current directory."""

    COLUMN_LABELS = ("Sel", "Type", "Name", "Size", "Modified")
    SELECTED_STYLE = "bold green"

    def __init__(
        self,
        title: str,
        entries: Sequence[PaneEntry],
        cursor_index: int | None = None,
        *,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes)
        self._title = title
        self._entries = tuple(entries)
        self._cursor_index = cursor_index

    @property
    def table_id(self) -> str | None:
        """Return the derived table identifier for tests and styling."""
        return f"{self.id}-table" if self.id else None

    def compose(self) -> ComposeResult:
        yield Label(self._title, classes="pane-title")
        yield DataTable(id=self.table_id, classes="pane-table")

    def on_mount(self) -> None:
        """Populate the table after the widget is attached to an app."""
        table = self.query_one(DataTable)
        table.cursor_type = "row"
        table.show_cursor = True
        table.zebra_stripes = True
        table.add_columns(*self.COLUMN_LABELS)
        self.set_entries(self._entries, self._cursor_index)

    def set_entries(
        self,
        entries: Sequence[PaneEntry],
        cursor_index: int | None = None,
    ) -> None:
        """Replace the rendered rows without remounting the pane."""

        next_entries = tuple(entries)
        if next_entries == self._entries and cursor_index == self._cursor_index:
            return

        self._entries = next_entries
        self._cursor_index = cursor_index
        table = self.query_one(DataTable)
        table.clear()
        for entry in self._entries:
            table.add_row(
                self._render_cell(entry.selection_marker, entry.selected),
                self._render_cell(entry.kind_label, entry.selected),
                self._render_cell(entry.name, entry.selected),
                self._render_cell(entry.size_label, entry.selected),
                self._render_cell(entry.modified_label, entry.selected),
            )
        self._sync_cursor(table)

    def _sync_cursor(self, table: DataTable) -> None:
        if not self._entries or self._cursor_index is None:
            return
        clamped_index = max(0, min(len(self._entries) - 1, self._cursor_index))
        table.move_cursor(row=clamped_index, animate=False, scroll=True)

    @classmethod
    def _render_cell(cls, value: str, selected: bool) -> Text:
        if not selected:
            return Text(value)
        return Text(value, style=cls.SELECTED_STYLE)
