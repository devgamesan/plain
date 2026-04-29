"""Main pane widget for the current directory table view."""

from collections.abc import Sequence
from dataclasses import replace

from rich.style import Style
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.css.query import NoMatches
from textual.widgets import DataTable, Label

from zivo.models.shell_data import (
    CurrentPaneRowUpdate,
    CurrentPaneSizeUpdate,
    CurrentSummaryState,
    InputBarState,
    PaneEntry,
)

from .input_bar import InputBar
from .pane_rendering import (
    FILE_TYPE_COMPONENT_CLASSES,
    _ft_resolve_style,
    _resolve_component_styles,
    _style_without_background,
    build_entry_label,
    truncate_middle,
)
from .summary_bar import SummaryBar


class MainPane(Vertical):
    """Center pane with detailed columns for the current directory."""

    COLUMN_LABELS = ("Sel", "Name", "Size", "Modified")
    COLUMN_KEYS = ("sel", "name", "size", "modified")
    COMPONENT_CLASSES = FILE_TYPE_COMPONENT_CLASSES
    NAME_MIN_WIDTH = 3
    FIXED_COLUMN_PREFERRED_WIDTHS = {
        "sel": 1,
        "size": 9,
        "modified": 16,
    }
    FIXED_COLUMN_MIN_WIDTHS = {
        "sel": 1,
        "size": 4,
        "modified": 5,
    }
    FIXED_COLUMN_SHRINK_ORDER = ("modified", "size", "sel")
    ROW_KEY_PREFIX = "__slot__:"

    def __init__(
        self,
        title: str,
        entries: Sequence[PaneEntry],
        summary: CurrentSummaryState,
        cursor_index: int | None = None,
        cursor_visible: bool = True,
        context_input: InputBarState | None = None,
        *,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes)
        self._title = title
        self._entries = tuple(entries)
        self._summary = summary
        self._cursor_index = cursor_index
        self._cursor_visible = cursor_visible
        self._context_input = context_input
        self._ft_styles: dict[str, Style] = {}
        self._last_table_width = 0

    @property
    def table_id(self) -> str | None:
        """Return the derived table identifier for tests and styling."""
        return f"{self.id}-table" if self.id else None

    @property
    def context_input_id(self) -> str | None:
        """Return the derived context input identifier for tests and styling."""

        return f"{self.id}-context-input" if self.id else None

    @property
    def summary_id(self) -> str | None:
        """Return the derived summary widget identifier for tests and styling."""

        return f"{self.id}-summary-bar" if self.id else None

    def compose(self) -> ComposeResult:
        yield Label(self._title, classes="pane-title")
        yield SummaryBar(self._summary, id=self.summary_id, classes="pane-summary")
        yield InputBar(self._context_input, id=self.context_input_id, classes="pane-context-input")
        yield DataTable(id=self.table_id, classes="pane-table")

    def on_mount(self) -> None:
        """Populate the table after the widget is attached to an app."""
        self._ft_styles = _resolve_component_styles(self)
        table = self.query_one(DataTable)
        table.cursor_type = "row"
        table.show_cursor = self._cursor_visible
        table.zebra_stripes = True
        self._rebuild_table(table)
        self._apply_cursor_state(table)
        self.call_after_refresh(self._refresh_table_width)

    def on_resize(self, _event: events.Resize) -> None:
        self._refresh_table_width()

    def set_entries(
        self,
        entries: Sequence[PaneEntry],
        cursor_index: int | None = None,
    ) -> None:
        """Replace the rendered rows without remounting the pane."""

        next_entries = tuple(entries)
        entries_changed = next_entries != self._entries
        cursor_changed = cursor_index != self._cursor_index
        if not entries_changed and not cursor_changed:
            return

        previous_entries = self._entries
        self._entries = next_entries
        self._cursor_index = cursor_index
        table = self.query_one(DataTable)
        if entries_changed:
            if self._should_rebuild_rows(table, previous_entries, next_entries):
                self._rebuild_table(table)
            else:
                self._update_changed_rows(table, previous_entries, next_entries)
        if entries_changed or cursor_changed:
            self._apply_cursor_state(table)

    def set_cursor_state(
        self,
        cursor_index: int | None,
        cursor_visible: bool,
        *,
        force_sync: bool = False,
    ) -> None:
        """Update cursor position and visibility without rebuilding rows."""

        cursor_changed = cursor_index != self._cursor_index
        visibility_changed = cursor_visible != self._cursor_visible
        if not force_sync and not cursor_changed and not visibility_changed:
            return

        self._cursor_index = cursor_index
        self._cursor_visible = cursor_visible
        table = self.query_one(DataTable)
        self._apply_cursor_state(table)

    def _sync_cursor(self, table: DataTable) -> None:
        if not self._entries or self._cursor_index is None:
            return
        clamped_index = max(0, min(len(self._entries) - 1, self._cursor_index))
        table.move_cursor(row=clamped_index, animate=False, scroll=True)

    def _apply_cursor_state(self, table: DataTable) -> None:
        table.show_cursor = self._cursor_visible
        self._sync_cursor(table)

    def set_context_input(self, state: InputBarState | None) -> None:
        """Update the contextual input line without remounting the pane."""

        if state == self._context_input:
            return

        self._context_input = state
        self.query_one(InputBar).set_state(state)

    def set_summary(self, state: CurrentSummaryState) -> None:
        """Update the summary line without remounting the pane."""

        if state == self._summary:
            return

        self._summary = state
        self.query_one(SummaryBar).set_state(state)

    def apply_size_updates(self, updates: Sequence[CurrentPaneSizeUpdate]) -> None:
        """Update only the size cells for the supplied paths."""

        if not updates:
            return

        changed_rows: list[tuple[str, PaneEntry]] = []
        next_entries: list[PaneEntry] = []
        update_by_row = {
            row_index: size_label
            for row_index, size_label in (
                (self._resolve_row_index(update.row_index, update.path), update.size_label)
                for update in updates
            )
            if row_index is not None
        }
        for row_index, entry in enumerate(self._entries):
            next_size_label = update_by_row.get(row_index)
            if next_size_label is None or next_size_label == entry.size_label:
                next_entries.append(entry)
                continue
            next_entry = replace(entry, size_label=next_size_label)
            next_entries.append(next_entry)
            changed_rows.append((self._slot_row_key(row_index), next_entry))

        if not changed_rows:
            return

        self._entries = tuple(next_entries)
        table = self.query_one(DataTable)
        for row_key, entry in changed_rows:
            try:
                table.update_cell(row_key, "size", self._render_cell(entry.size_label, entry))
            except KeyError:
                continue

    def apply_row_updates(self, updates: Sequence[CurrentPaneRowUpdate]) -> None:
        """Update only the supplied rows without rebuilding the table."""

        if not updates:
            return

        changed_rows: list[tuple[str, PaneEntry]] = []
        next_entries: list[PaneEntry] = []
        update_by_row = {
            row_index: entry
            for row_index, entry in (
                (self._resolve_row_index(update.row_index, update.path), update.entry)
                for update in updates
            )
            if row_index is not None
        }
        for row_index, entry in enumerate(self._entries):
            next_entry = update_by_row.get(row_index)
            if next_entry is None or next_entry == entry:
                next_entries.append(entry)
                continue
            next_entries.append(next_entry)
            changed_rows.append((self._slot_row_key(row_index), next_entry))

        if not changed_rows:
            return

        self._entries = tuple(next_entries)
        table = self.query_one(DataTable)
        column_widths = self._allocate_column_widths(table)
        for row_key, entry in changed_rows:
            next_cells = self._build_row_cells(entry, column_widths)
            for column_key, next_cell in zip(
                self.COLUMN_KEYS,
                next_cells,
                strict=False,
            ):
                try:
                    table.update_cell(row_key, column_key, next_cell)
                except KeyError:
                    continue

    def _refresh_table_width(self) -> None:
        try:
            table = self.query_one(DataTable)
        except NoMatches:
            return
        table_width = table.size.width
        if table_width <= 0 or table_width == self._last_table_width:
            return
        self._rebuild_table(table)

    def _should_rebuild_rows(
        self,
        table: DataTable,
        previous_entries: Sequence[PaneEntry],
        next_entries: Sequence[PaneEntry],
    ) -> bool:
        if table.size.width != self._last_table_width:
            return True
        if len(previous_entries) != len(next_entries):
            return True
        return False

    def _update_changed_rows(
        self,
        table: DataTable,
        previous_entries: Sequence[PaneEntry],
        next_entries: Sequence[PaneEntry],
    ) -> None:
        column_widths = self._allocate_column_widths(table)
        for index, (previous_entry, next_entry) in enumerate(
            zip(previous_entries, next_entries, strict=False)
        ):
            if previous_entry == next_entry:
                continue
            next_cells = self._build_row_cells(next_entry, column_widths)
            row_key = self._slot_row_key(index)
            for column_key, next_cell in zip(
                self.COLUMN_KEYS,
                next_cells,
                strict=False,
            ):
                table.update_cell(row_key, column_key, next_cell)

    def _rebuild_table(self, table: DataTable) -> None:
        column_widths = self._allocate_column_widths(table)
        table.clear(columns=True)
        table.add_column(
            self.COLUMN_LABELS[0], width=column_widths["sel"], key=self.COLUMN_KEYS[0]
        )
        table.add_column(
            self.COLUMN_LABELS[1], width=column_widths["name"], key=self.COLUMN_KEYS[1]
        )
        table.add_column(
            self.COLUMN_LABELS[2], width=column_widths["size"], key=self.COLUMN_KEYS[2]
        )
        table.add_column(
            self.COLUMN_LABELS[3],
            width=column_widths["modified"],
            key=self.COLUMN_KEYS[3],
        )
        for index, entry in enumerate(self._entries):
            table.add_row(
                *self._build_row_cells(entry, column_widths),
                key=self._slot_row_key(index),
            )
        self._last_table_width = table.size.width

    @classmethod
    def _entry_row_keys(cls, entries: Sequence[PaneEntry]) -> tuple[str, ...]:
        return tuple(cls._slot_row_key(index) for index, _ in enumerate(entries))

    @staticmethod
    def _slot_row_key(index: int) -> str:
        return f"{MainPane.ROW_KEY_PREFIX}{index}"

    def _resolve_row_index(self, row_index: int, path: str) -> int | None:
        if 0 <= row_index < len(self._entries):
            if not path or self._entries[row_index].path == path:
                return row_index
        if not path:
            return None
        for index, entry in enumerate(self._entries):
            if entry.path == path:
                return index
        return None

    def _build_row_cells(
        self,
        entry: PaneEntry,
        column_widths: dict[str, int],
    ) -> tuple[Text, Text, Text, Text]:
        return (
            self._render_cell(entry.selection_marker, entry),
            self._render_cell(
                truncate_middle(build_entry_label(entry), column_widths["name"]),
                entry,
            ),
            self._render_cell(entry.size_label, entry),
            self._render_cell(entry.modified_label, entry),
        )

    @classmethod
    def _allocate_column_widths(cls, table: DataTable) -> dict[str, int]:
        column_count = len(cls.COLUMN_LABELS)
        padding_width = column_count * table.cell_padding * 2
        available_content_width = max(1, table.size.width - padding_width)
        fixed_widths = cls._shrink_fixed_columns(available_content_width)
        name_width = max(1, available_content_width - sum(fixed_widths.values()))
        return {
            "sel": fixed_widths["sel"],
            "name": name_width,
            "size": fixed_widths["size"],
            "modified": fixed_widths["modified"],
        }

    @classmethod
    def _shrink_fixed_columns(cls, available_content_width: int) -> dict[str, int]:
        fixed_widths = dict(cls.FIXED_COLUMN_PREFERRED_WIDTHS)
        fixed_budget = max(0, available_content_width - cls.NAME_MIN_WIDTH)
        overflow = sum(fixed_widths.values()) - fixed_budget
        for column_key in cls.FIXED_COLUMN_SHRINK_ORDER:
            if overflow <= 0:
                break
            reducible = fixed_widths[column_key] - cls.FIXED_COLUMN_MIN_WIDTHS[column_key]
            if reducible <= 0:
                continue
            shrink_by = min(reducible, overflow)
            fixed_widths[column_key] -= shrink_by
            overflow -= shrink_by

        if sum(fixed_widths.values()) + cls.NAME_MIN_WIDTH > available_content_width:
            fixed_widths = dict(cls.FIXED_COLUMN_MIN_WIDTHS)

        return fixed_widths

    def _entry_style(self, entry: PaneEntry) -> Style | None:
        return _style_without_background(
            _ft_resolve_style(
                entry,
                self._ft_styles,
                selected_directory_style="ft-directory-sel-table",
                selected_cut_style="ft-selected-cut",
            )
        )

    def _render_cell(self, value: str, entry: PaneEntry) -> Text:
        style = self._entry_style(entry)
        return Text(value) if style is None else Text(value, style=style)

    def refresh_styles(self) -> None:
        """Re-resolve component styles after a theme change."""

        self._ft_styles = _resolve_component_styles(self)
        self._rebuild_table(self.query_one(DataTable))
