"""Reusable widgets for the initial three-pane shell."""

from collections.abc import Sequence

from rich.cells import cell_len
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.css.query import NoMatches
from textual.widgets import DataTable, Label, ListItem, ListView

from peneo.models.shell_data import CurrentSummaryState, InputBarState, PaneEntry

from .input_bar import InputBar
from .summary_bar import SummaryBar

ELLIPSIS = "~"


def build_entry_label(entry: PaneEntry) -> str:
    """Return the complete entry label before width-based truncation."""

    if entry.name_detail is None:
        return entry.name
    return f"{entry.name}  ({entry.name_detail})"


def truncate_middle(text: str, max_width: int) -> str:
    """Shorten text with a middle marker while preserving a useful suffix."""

    if max_width <= 0:
        return ""
    if cell_len(text) <= max_width:
        return text
    if max_width == 1:
        return ELLIPSIS
    if max_width == 2:
        return f"{ELLIPSIS}{_take_suffix_cells(text, 1)}"

    remaining_width = max_width - cell_len(ELLIPSIS)
    preferred_suffix = _preferred_suffix(text)
    if preferred_suffix and cell_len(preferred_suffix) <= remaining_width - 1:
        suffix_width = cell_len(preferred_suffix)
    else:
        suffix_width = max(1, remaining_width // 2)
    prefix_width = remaining_width - suffix_width
    if prefix_width <= 0:
        prefix_width = 1
        suffix_width = remaining_width - prefix_width

    prefix = _take_prefix_cells(text, prefix_width)
    suffix = _take_suffix_cells(text, suffix_width)
    return f"{prefix}{ELLIPSIS}{suffix}"


def _preferred_suffix(text: str) -> str:
    dot_index = text.rfind(".")
    if dot_index <= 0 or dot_index == len(text) - 1:
        return ""
    return text[dot_index:]


def _take_prefix_cells(text: str, width: int) -> str:
    if width <= 0:
        return ""
    collected: list[str] = []
    used_width = 0
    for character in text:
        character_width = cell_len(character)
        if used_width + character_width > width:
            break
        collected.append(character)
        used_width += character_width
    return "".join(collected)


def _take_suffix_cells(text: str, width: int) -> str:
    if width <= 0:
        return ""
    collected: list[str] = []
    used_width = 0
    for character in reversed(text):
        character_width = cell_len(character)
        if used_width + character_width > width:
            break
        collected.append(character)
        used_width += character_width
    return "".join(reversed(collected))


class SidePane(Vertical):
    """Lightweight pane used for parent and child directory listings."""

    CUT_STYLE = "bright_black dim"
    EXECUTABLE_STYLE = "cyan"
    EXECUTABLE_SELECTED_STYLE = "bold cyan"
    EXECUTABLE_CUT_STYLE = "cyan dim"
    DIRECTORY_STYLE = "blue"
    DIRECTORY_SELECTED_STYLE = "bold blue"
    DIRECTORY_CUT_STYLE = "blue dim"
    ENTRY_HORIZONTAL_PADDING = 2

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
        self._last_render_width = 0

    @property
    def list_view_id(self) -> str | None:
        """Return the derived list view identifier for tests and styling."""
        return f"{self.id}-list" if self.id else None

    def compose(self) -> ComposeResult:
        yield Label(self._title, classes="pane-title")
        list_view = ListView(
            *self._build_items(self._entries, 0),
            id=self.list_view_id,
            classes="pane-list",
        )
        list_view.can_focus = False
        yield list_view

    def on_mount(self) -> None:
        self.call_after_refresh(self._refresh_rendered_labels)

    def on_resize(self, _event: events.Resize) -> None:
        self._refresh_rendered_labels()

    async def set_entries(self, entries: Sequence[PaneEntry]) -> None:
        """Replace the rendered entries without remounting the pane."""

        next_entries = tuple(entries)
        if next_entries == self._entries:
            return

        list_view = self.query_one(ListView)
        render_width = self._entry_width(list_view)
        previous_entries = self._entries
        previous_items = tuple(list_view.children)
        if any(not self._item_has_label(item) for item in previous_items):
            await self._rebuild_items(list_view, next_entries, render_width)
            self._entries = next_entries
            self._last_render_width = render_width
            return

        shared_count = min(len(previous_items), len(previous_entries), len(next_entries))
        for index in range(shared_count):
            if (
                previous_entries[index] == next_entries[index]
                and render_width == self._last_render_width
            ):
                continue
            self._update_item(previous_items[index], next_entries[index], render_width)

        if len(previous_items) > len(next_entries):
            for item in previous_items[len(next_entries) :]:
                await item.remove()
        elif len(previous_items) < len(next_entries):
            items = self._build_items(next_entries[len(previous_items) :], render_width)
            if items:
                await list_view.extend(items)

        self._entries = next_entries
        self._last_render_width = render_width

    def _refresh_rendered_labels(self) -> None:
        list_view = self.query_one(ListView)
        render_width = self._entry_width(list_view)
        if render_width <= 0 or render_width == self._last_render_width:
            return
        for item, entry in zip(list_view.children, self._entries, strict=False):
            self._update_item(item, entry, render_width)
        self._last_render_width = render_width

    @classmethod
    def _update_item(cls, item: ListItem, entry: PaneEntry, render_width: int) -> None:
        try:
            item.query_one(Label).update(cls._render_label(entry, render_width))
        except NoMatches:
            pass

    @staticmethod
    def _item_has_label(item: ListItem) -> bool:
        try:
            item.query_one(Label)
        except NoMatches:
            return False
        return True

    @classmethod
    async def _rebuild_items(
        cls,
        list_view: ListView,
        entries: Sequence[PaneEntry],
        render_width: int,
    ) -> None:
        await list_view.clear()
        items = cls._build_items(entries, render_width)
        if items:
            await list_view.extend(items)

    @classmethod
    def _build_items(cls, entries: Sequence[PaneEntry], render_width: int) -> tuple[ListItem, ...]:
        return tuple(
            ListItem(
                Label(cls._render_label(entry, render_width), classes="pane-entry-label"),
                classes="pane-entry",
            )
            for entry in entries
        )

    @classmethod
    def _render_label(cls, entry: PaneEntry, render_width: int = 0) -> Text:
        label = build_entry_label(entry)
        if render_width > 0:
            label = truncate_middle(label, render_width)

        # カット状態が最優先
        if entry.cut:
            if entry.kind == "dir":
                return Text(label, style=cls.DIRECTORY_CUT_STYLE)
            if entry.executable:
                return Text(label, style=cls.EXECUTABLE_CUT_STYLE)
            return Text(label, style=cls.CUT_STYLE)

        # ディレクトリ（実行権限に関わらずディレクトリ色を優先）
        if entry.kind == "dir":
            if entry.selected:
                return Text(label, style=cls.DIRECTORY_SELECTED_STYLE)
            return Text(label, style=cls.DIRECTORY_STYLE)

        # 実行権限付きファイル
        if entry.executable:
            if entry.selected:
                return Text(label, style=cls.EXECUTABLE_SELECTED_STYLE)
            return Text(label, style=cls.EXECUTABLE_STYLE)

        # 選択状態
        if entry.selected:
            return Text(label, style="bold green")

        return Text(label)

    def _entry_width(self, list_view: ListView) -> int:
        return max(0, list_view.size.width - self.ENTRY_HORIZONTAL_PADDING)


class MainPane(Vertical):
    """Center pane with detailed columns for the current directory."""

    COLUMN_LABELS = ("Sel", "Name", "Size", "Modified")
    COLUMN_KEYS = ("sel", "name", "size", "modified")
    SELECTED_STYLE = "bold green"
    CUT_STYLE = "bright_black dim"
    SELECTED_CUT_STYLE = "bold bright_black"
    EXECUTABLE_STYLE = "cyan"
    EXECUTABLE_SELECTED_STYLE = "bold cyan"
    EXECUTABLE_CUT_STYLE = "cyan dim"
    DIRECTORY_STYLE = "blue"
    DIRECTORY_SELECTED_STYLE = "bold blue"
    DIRECTORY_CUT_STYLE = "blue dim"
    NAME_MIN_WIDTH = 3
    FIXED_COLUMN_PREFERRED_WIDTHS = {
        "sel": 1,
        "size": 13,
        "modified": 16,
    }
    FIXED_COLUMN_MIN_WIDTHS = {
        "sel": 1,
        "size": 4,
        "modified": 5,
    }
    FIXED_COLUMN_SHRINK_ORDER = ("modified", "size", "sel")

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
        self.call_after_refresh(self._refresh_cursor_state)

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

    def _sync_cursor(self, table: DataTable) -> None:
        if not self._entries or self._cursor_index is None:
            return
        clamped_index = max(0, min(len(self._entries) - 1, self._cursor_index))
        table.move_cursor(row=clamped_index, animate=False, scroll=True)

    def _apply_cursor_state(self, table: DataTable) -> None:
        table.show_cursor = self._cursor_visible
        self._sync_cursor(table)

    def _refresh_cursor_state(self) -> None:
        self._apply_cursor_state(self.query_one(DataTable))

    def _refresh_table_width(self) -> None:
        table = self.query_one(DataTable)
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
        return self._entry_row_keys(previous_entries) != self._entry_row_keys(next_entries)

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
            row_key = self._row_key(next_entry, index)
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
                key=self._row_key(entry, index),
            )
        self._last_table_width = table.size.width

    @classmethod
    def _entry_row_keys(cls, entries: Sequence[PaneEntry]) -> tuple[str, ...]:
        return tuple(cls._row_key(entry, index) for index, entry in enumerate(entries))

    @staticmethod
    def _row_key(entry: PaneEntry, index: int) -> str:
        return entry.path or f"__row__:{index}"

    @classmethod
    def _build_row_cells(
        cls,
        entry: PaneEntry,
        column_widths: dict[str, int],
    ) -> tuple[Text, Text, Text, Text]:
        return (
            cls._render_cell(
                entry.selection_marker,
                entry.selected,
                entry.cut,
                entry.executable,
                entry.kind,
            ),
            cls._render_cell(
                truncate_middle(build_entry_label(entry), column_widths["name"]),
                entry.selected,
                entry.cut,
                entry.executable,
                entry.kind,
            ),
            cls._render_cell(
                entry.size_label,
                entry.selected,
                entry.cut,
                entry.executable,
                entry.kind,
            ),
            cls._render_cell(
                entry.modified_label,
                entry.selected,
                entry.cut,
                entry.executable,
                entry.kind,
            ),
        )

    @classmethod
    def _allocate_column_widths(cls, table: DataTable) -> dict[str, int]:
        column_count = len(cls.COLUMN_LABELS)
        padding_width = column_count * table.cell_padding * 2
        available_content_width = max(1, table.size.width - padding_width)

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

        name_width = max(1, available_content_width - sum(fixed_widths.values()))
        return {
            "sel": fixed_widths["sel"],
            "name": name_width,
            "size": fixed_widths["size"],
            "modified": fixed_widths["modified"],
        }

    @classmethod
    def _render_cell(
        cls,
        value: str,
        selected: bool,
        cut: bool,
        executable: bool = False,
        kind: str | None = None,
    ) -> Text:
        # カット状態が最優先
        if cut:
            if kind == "dir":
                return Text(value, style=cls.DIRECTORY_CUT_STYLE)
            if executable:
                return Text(value, style=cls.EXECUTABLE_CUT_STYLE)
            if selected:
                return Text(value, style=cls.SELECTED_CUT_STYLE)
            return Text(value, style=cls.CUT_STYLE)

        # ディレクトリ（実行権限に関わらずディレクトリ色を優先）
        if kind == "dir":
            if selected:
                return Text(value, style=cls.DIRECTORY_SELECTED_STYLE)
            return Text(value, style=cls.DIRECTORY_STYLE)

        # 実行権限付きファイル
        if executable:
            if selected:
                return Text(value, style=cls.EXECUTABLE_SELECTED_STYLE)
            return Text(value, style=cls.EXECUTABLE_STYLE)

        # 選択状態
        if selected:
            return Text(value, style=cls.SELECTED_STYLE)

        return Text(value)
