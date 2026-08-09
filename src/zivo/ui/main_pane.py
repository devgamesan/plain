"""Main pane widget for the current directory table view."""

from collections.abc import Sequence
from dataclasses import replace

from rich.style import Style
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.css.query import NoMatches
from textual.message import Message
from textual.widgets import DataTable, Label, Static

from zivo.models.shell_data import (
    CurrentPaneRowUpdate,
    CurrentPaneSizeUpdate,
    CurrentSummaryState,
    InputBarState,
    PaneEntry,
    PaneHeadingState,
    PaneStatusViewState,
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
from .pane_status import render_pane_status
from .summary_bar import SummaryBar


class _MainPaneDataTable(DataTable):
    """DataTable variant that forwards mouse row clicks to its owning MainPane."""

    async def _on_click(self, event: events.Click) -> None:
        meta = event.style.meta
        await super()._on_click(event)
        row_index = meta.get("row")
        column_index = meta.get("column")
        if not isinstance(row_index, int) or not isinstance(column_index, int):
            return
        if row_index < 0 or column_index < 0:
            return
        event.stop()
        handler = getattr(self.parent, "handle_table_row_clicked", None)
        if handler is None:
            return
        await handler(row_index)

    def _on_mouse_move(self, event: events.MouseMove) -> None:
        super()._on_mouse_move(event)
        self._set_hover_cursor(False)


class MainPane(Vertical):
    """Center pane with detailed columns for the current directory."""

    COLUMN_LABELS = ("State", "Name", "Size", "Modified")
    COLUMN_KEYS = ("sel", "name", "size", "modified")
    COMPONENT_CLASSES = FILE_TYPE_COMPONENT_CLASSES
    NAME_MIN_WIDTH = 3
    FIXED_COLUMN_PREFERRED_WIDTHS = {
        "sel": 2,
        "size": 9,
        "modified": 16,
    }
    FIXED_COLUMN_MIN_WIDTHS = {
        "sel": 2,
        "size": 4,
        "modified": 5,
    }
    FIXED_COLUMN_SHRINK_ORDER = ("modified", "size", "sel")
    ROW_KEY_PREFIX = "__slot__:"
    class EntryClicked(Message):
        """Notify the app that a pane row was clicked."""

        def __init__(self, pane_id: str | None, path: str, *, double_click: bool) -> None:
            super().__init__()
            self.pane_id = pane_id
            self.path = path
            self.double_click = double_click

    class PaneClicked(Message):
        """Notify the app that a transfer pane was clicked (not on a specific row)."""

        def __init__(self, pane_id: str | None) -> None:
            super().__init__()
            self.pane_id = pane_id

    class ActionClicked(Message):
        """Notify the app that an inline empty-state action was clicked."""

        def __init__(self, action_id: str) -> None:
            super().__init__()
            self.action_id = action_id

    def __init__(
        self,
        title: str,
        entries: Sequence[PaneEntry],
        summary: CurrentSummaryState,
        cursor_index: int | None = None,
        cursor_visible: bool = True,
        context_input: InputBarState | None = None,
        status: PaneStatusViewState | None = None,
        heading: PaneHeadingState | None = None,
        *,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes)
        self._title = title
        self._heading = heading
        self._entries = tuple(entries)
        self._path_row_index = self._build_path_row_index(self._entries)
        self._summary = summary
        self._cursor_index = cursor_index
        self._cursor_visible = cursor_visible
        self._context_input = context_input
        self._status = status
        self._ft_styles: dict[str, Style] = {}
        self._last_table_width = 0
        self._last_clicked_path: str | None = None

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
        yield Label(self._heading_text(), classes="pane-title")
        yield SummaryBar(self._summary, id=self.summary_id, classes="pane-summary")
        yield InputBar(self._context_input, id=self.context_input_id, classes="pane-context-input")
        table = _MainPaneDataTable(id=self.table_id, classes="pane-table")
        yield table
        status = Static(
            render_pane_status(self._status),
            id=f"{self.id}-status" if self.id else None,
            classes="pane-status",
        )
        status.display = self._status is not None
        yield status

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

    async def handle_table_row_clicked(self, row_index: int) -> None:
        """Synchronize app state for a row clicked in the inner table."""

        if row_index < 0 or row_index >= len(self._entries):
            return
        path = self._entries[row_index].path
        double_click = path == self._last_clicked_path
        self._last_clicked_path = path
        handler = getattr(self.app, "on_main_pane_entry_clicked", None)
        if handler is None:
            return
        await handler(self.EntryClicked(self.id, path, double_click=double_click))

    async def on_click(self, event: events.Click) -> None:
        """In transfer mode, clicking on the pane switches focus to it."""

        action_id = event.style.meta.get("pane_action_id")
        if action_id is not None:
            event.stop()
            self.post_message(self.ActionClicked(str(action_id)))
            return
        if "transfer-pane" not in self.classes:
            return
        handler = getattr(self.app, "on_main_pane_pane_clicked", None)
        if handler is None:
            return
        await handler(self.PaneClicked(self.id))

    def set_status(self, status: PaneStatusViewState | None) -> None:
        if status == self._status:
            return
        self._status = status
        table = self.query_one(DataTable)
        status_widget = self.query_one(".pane-status", Static)
        status_widget.display = status is not None
        status_widget.update(render_pane_status(status))
        if status is None:
            self._apply_cursor_state(table)
            self.call_after_refresh(lambda: self._apply_cursor_state(table))

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
        previous_cursor_index = self._cursor_index
        self._entries = next_entries
        self._path_row_index = self._build_path_row_index(self._entries)
        self._cursor_index = cursor_index
        table = self.query_one(DataTable)
        if entries_changed:
            if self._should_rebuild_rows(table, previous_entries, next_entries):
                self._rebuild_table(table)
            else:
                self._update_changed_rows(table, previous_entries, next_entries)
            self._clear_hover_cursor(table)
        if cursor_changed and not entries_changed:
            self._update_cursor_markers(table, previous_cursor_index, self._cursor_index)
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

        previous_cursor_index = self._cursor_index
        self._cursor_index = cursor_index
        self._cursor_visible = cursor_visible
        table = self.query_one(DataTable)
        if cursor_changed:
            self._update_cursor_markers(table, previous_cursor_index, cursor_index)
        self._apply_cursor_state(table)

    def set_heading(self, heading: PaneHeadingState | None) -> None:
        """Update the semantic pane heading without remounting the pane."""

        if heading == self._heading:
            return
        self._heading = heading
        self.query_one(".pane-title", Label).update(self._heading_text())

    def _heading_text(self) -> str:
        if self._heading is None:
            return self._title
        marker = ">" if self._heading.active else " "
        return f"{marker} {self._heading.role} — {self._heading.target_name}"

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
        next_entries: list[PaneEntry] | None = None
        update_by_row = {
            row_index: size_label
            for row_index, size_label in (
                (self._resolve_row_index(update.row_index, update.path), update.size_label)
                for update in updates
            )
            if row_index is not None
        }
        for row_index, next_size_label in update_by_row.items():
            entry = self._entries[row_index]
            if next_size_label == entry.size_label:
                continue
            if next_entries is None:
                next_entries = list(self._entries)
            next_entry = replace(entry, size_label=next_size_label)
            next_entries[row_index] = next_entry
            changed_rows.append((self._slot_row_key(row_index), next_entry))

        if not changed_rows:
            return

        self._entries = tuple(next_entries)
        self._path_row_index = self._build_path_row_index(self._entries)
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
        next_entries: list[PaneEntry] | None = None
        update_by_row = {
            row_index: entry
            for row_index, entry in (
                (self._resolve_row_index(update.row_index, update.path), update.entry)
                for update in updates
            )
            if row_index is not None
        }
        for row_index, next_entry in update_by_row.items():
            entry = self._entries[row_index]
            if next_entry == entry:
                continue
            if next_entries is None:
                next_entries = list(self._entries)
            next_entries[row_index] = next_entry
            changed_rows.append((self._slot_row_key(row_index), next_entry))

        if not changed_rows:
            return

        self._entries = tuple(next_entries)
        self._path_row_index = self._build_path_row_index(self._entries)
        table = self.query_one(DataTable)
        column_widths = self._allocate_column_widths(table)
        for row_key, entry in changed_rows:
            row_index = self._path_row_index.get(entry.path)
            next_cells = self._build_row_cells(entry, column_widths, row_index=row_index)
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
            next_cells = self._build_row_cells(next_entry, column_widths, row_index=index)
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
                *self._build_row_cells(entry, column_widths, row_index=index),
                key=self._slot_row_key(index),
            )
        self._last_table_width = table.size.width
        self._clear_hover_cursor(table)

    @staticmethod
    def _clear_hover_cursor(table: DataTable) -> None:
        table._set_hover_cursor(False)

    @classmethod
    def _entry_row_keys(cls, entries: Sequence[PaneEntry]) -> tuple[str, ...]:
        return tuple(cls._slot_row_key(index) for index, _ in enumerate(entries))

    @staticmethod
    def _slot_row_key(index: int) -> str:
        return f"{MainPane.ROW_KEY_PREFIX}{index}"

    @staticmethod
    def _build_path_row_index(entries: Sequence[PaneEntry]) -> dict[str, int]:
        path_row_index: dict[str, int] = {}
        for index, entry in enumerate(entries):
            if entry.path and entry.path not in path_row_index:
                path_row_index[entry.path] = index
        return path_row_index

    def _resolve_row_index(self, row_index: int, path: str) -> int | None:
        if 0 <= row_index < len(self._entries):
            if not path or self._entries[row_index].path == path:
                return row_index
        if not path:
            return None
        return self._path_row_index.get(path)

    def _build_row_cells(
        self,
        entry: PaneEntry,
        column_widths: dict[str, int],
        *,
        row_index: int | None = None,
    ) -> tuple[Text, Text, Text, Text]:
        return (
            self._render_cell(
                entry.state_marker(cursor=row_index == self._cursor_index, max_width=2),
                entry,
            ),
            self._render_cell(
                truncate_middle(build_entry_label(entry), column_widths["name"]),
                entry,
            ),
            self._render_cell(entry.size_label, entry),
            self._render_cell(entry.modified_label, entry),
        )

    def _update_cursor_markers(
        self,
        table: DataTable,
        previous_index: int | None,
        next_index: int | None,
    ) -> None:
        """Refresh only state cells affected by a cursor move."""

        for row_index in {previous_index, next_index}:
            if row_index is None or not 0 <= row_index < len(self._entries):
                continue
            entry = self._entries[row_index]
            try:
                table.update_cell(
                    self._slot_row_key(row_index),
                    "sel",
                    self._render_cell(
                        entry.state_marker(cursor=row_index == next_index, max_width=2),
                        entry,
                    ),
                )
            except KeyError:
                continue

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
