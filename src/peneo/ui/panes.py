"""Reusable widgets for the initial three-pane shell."""

from collections.abc import Sequence
from dataclasses import replace

from rich.cells import cell_len
from rich.syntax import Syntax
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import DataTable, Label, Static

from peneo.models.shell_data import (
    ChildPaneViewState,
    CurrentPaneRowUpdate,
    CurrentPaneSizeUpdate,
    CurrentSummaryState,
    InputBarState,
    PaneEntry,
)

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
    EXECUTABLE_STYLE = "bold #55FF55"
    EXECUTABLE_SELECTED_STYLE = "bold #55FF55"
    EXECUTABLE_CUT_STYLE = "bold #55FF55 dim"
    DIRECTORY_STYLE = "bold #5555FF"
    DIRECTORY_SELECTED_STYLE = "bold white on #5555FF"
    DIRECTORY_CUT_STYLE = "bold #5555FF dim"
    SYMLINK_STYLE = "bold #55FFFF"
    SYMLINK_SELECTED_STYLE = "bold #55FFFF"
    SYMLINK_CUT_STYLE = "bold #55FFFF dim"
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
        content = Static(
            self._render_entries(self._entries, 0),
            id=self.list_view_id,
            classes="pane-list",
        )
        content.can_focus = False
        yield content

    def on_mount(self) -> None:
        self.call_after_refresh(self._refresh_rendered_labels)

    def on_resize(self, _event: events.Resize) -> None:
        self._refresh_rendered_labels()

    async def set_entries(self, entries: Sequence[PaneEntry]) -> None:
        """Replace the rendered entries without remounting the pane."""

        next_entries = tuple(entries)
        if next_entries == self._entries:
            return

        content = self._content_widget()
        render_width = self._entry_width(content)
        content.update(self._render_entries(next_entries, render_width))
        self._entries = next_entries
        self._last_render_width = render_width

    def _refresh_rendered_labels(self) -> None:
        content = self._content_widget()
        render_width = self._entry_width(content)
        if render_width <= 0 or render_width == self._last_render_width:
            return
        content.update(self._render_entries(self._entries, render_width))
        self._last_render_width = render_width

    def _content_widget(self) -> Static:
        return self.query_one(f"#{self.list_view_id}", Static)

    @classmethod
    def _render_entries(cls, entries: Sequence[PaneEntry], render_width: int) -> Text:
        if not entries:
            return Text()
        return Text("\n").join(
            [cls._render_label(entry, render_width) for entry in entries]
        )

    @classmethod
    def _render_label(cls, entry: PaneEntry, render_width: int = 0) -> Text:
        label = build_entry_label(entry)
        if render_width > 0:
            label = truncate_middle(label, render_width)

        # カット状態が最優先
        if entry.cut:
            if entry.symlink:
                return Text(label, style=cls.SYMLINK_CUT_STYLE)
            if entry.kind == "dir":
                return Text(label, style=cls.DIRECTORY_CUT_STYLE)
            if entry.executable:
                return Text(label, style=cls.EXECUTABLE_CUT_STYLE)
            return Text(label, style=cls.CUT_STYLE)

        # シンボリックリンク
        if entry.symlink:
            if entry.selected:
                return Text(label, style=cls.SYMLINK_SELECTED_STYLE)
            return Text(label, style=cls.SYMLINK_STYLE)

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
            return Text(label, style="bold #55FF55")

        return Text(label)

    def _entry_width(self, content: Static) -> int:
        return max(0, content.size.width - self.ENTRY_HORIZONTAL_PADDING)


class ChildPane(Vertical):
    """Right-side pane that switches between entries and text preview."""

    PREVIEW_HORIZONTAL_PADDING = 2

    def __init__(
        self,
        state: ChildPaneViewState,
        *,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes)
        self._state = state
        self._last_render_width = 0

    @property
    def list_view_id(self) -> str | None:
        return f"{self.id}-list" if self.id else None

    @property
    def preview_id(self) -> str | None:
        return f"{self.id}-preview" if self.id else None

    @property
    def permissions_id(self) -> str | None:
        return f"{self.id}-permissions" if self.id else None

    def compose(self) -> ComposeResult:
        yield Label(self._state.title, classes="pane-title")
        list_content = Static(
            SidePane._render_entries(self._state.entries, 0),
            id=self.list_view_id,
            classes="pane-list",
        )
        list_content.can_focus = False
        preview_content = Static(
            self._render_preview(self._state, 0),
            id=self.preview_id,
            classes="pane-preview",
        )
        preview_content.can_focus = False
        preview_content.display = self._state.is_preview
        list_content.display = not self._state.is_preview
        yield list_content
        yield preview_content
        permissions = Static(
            self._state.permissions_label,
            id=self.permissions_id,
            classes="pane-permissions",
        )
        permissions.can_focus = False
        yield permissions

    def on_mount(self) -> None:
        self.call_after_refresh(self._refresh_rendered_content)

    def on_resize(self, _event: events.Resize) -> None:
        self._refresh_rendered_content()

    async def set_state(self, state: ChildPaneViewState) -> None:
        if state == self._state:
            return

        self._state = state
        self.query_one(Label).update(state.title)
        list_widget = self._list_widget()
        preview_widget = self._preview_widget()
        list_widget.display = not state.is_preview
        preview_widget.display = state.is_preview
        self._permissions_widget().update(state.permissions_label)
        self._last_render_width = 0
        self._refresh_rendered_content()
        self.call_after_refresh(self._refresh_rendered_content)

    def _refresh_rendered_content(self) -> None:
        if self._state.is_preview:
            widget = self._preview_widget()
            render_width = max(0, widget.size.width - self.PREVIEW_HORIZONTAL_PADDING)
            if render_width <= 0 or render_width == self._last_render_width:
                return
            widget.update(self._render_preview(self._state, render_width))
            self._last_render_width = render_width
            return

        widget = self._list_widget()
        render_width = max(0, widget.size.width - SidePane.ENTRY_HORIZONTAL_PADDING)
        if render_width <= 0 or render_width == self._last_render_width:
            return
        widget.update(SidePane._render_entries(self._state.entries, render_width))
        self._last_render_width = render_width

    def _list_widget(self) -> Static:
        return self.query_one(f"#{self.list_view_id}", Static)

    def _preview_widget(self) -> Static:
        return self.query_one(f"#{self.preview_id}", Static)

    def _permissions_widget(self) -> Static:
        return self.query_one(f"#{self.permissions_id}", Static)

    @staticmethod
    def _render_preview(state: ChildPaneViewState, render_width: int):
        if state.preview_message is not None:
            return Text(state.preview_message, style="italic dim")

        if state.preview_content is None:
            return Text()

        lexer = "text"
        if state.preview_path is not None:
            try:
                lexer = Syntax.guess_lexer(state.preview_path, code=state.preview_content)
            except Exception:
                lexer = "text"

        return Syntax(
            state.preview_content,
            lexer=lexer,
            theme=state.syntax_theme,
            word_wrap=False,
            line_numbers=state.preview_start_line is not None,
            start_line=state.preview_start_line or 1,
            highlight_lines=(
                {state.preview_highlight_line}
                if state.preview_highlight_line is not None
                else None
            ),
            code_width=max(1, render_width),
        )


class MainPane(Vertical):
    """Center pane with detailed columns for the current directory."""

    COLUMN_LABELS = ("Sel", "Name", "Size", "Modified")
    COLUMN_KEYS = ("sel", "name", "size", "modified")
    SELECTED_STYLE = "bold #55FF55"
    CUT_STYLE = "bright_black dim"
    SELECTED_CUT_STYLE = "bold bright_black"
    EXECUTABLE_STYLE = "bold #55FF55"
    EXECUTABLE_SELECTED_STYLE = "bold #55FF55"
    EXECUTABLE_CUT_STYLE = "bold #55FF55 dim"
    DIRECTORY_STYLE = "bold #5555FF"
    DIRECTORY_SELECTED_STYLE = "bold #5555FF"
    DIRECTORY_CUT_STYLE = "bold #5555FF dim"
    SYMLINK_STYLE = "bold #55FFFF"
    SYMLINK_SELECTED_STYLE = "bold #55FFFF"
    SYMLINK_CUT_STYLE = "bold #55FFFF dim"
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

    # -- Public state updates ---------------------------------------------------

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

    # -- Cursor management ------------------------------------------------------

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

    # -- Context input / summary ------------------------------------------------

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

    # -- Incremental updates ----------------------------------------------------

    def apply_size_updates(self, updates: Sequence[CurrentPaneSizeUpdate]) -> None:
        """Update only the size cells for the supplied paths."""

        if not updates:
            return

        update_by_path = {update.path: update.size_label for update in updates}
        changed_rows: list[tuple[str, PaneEntry]] = []
        next_entries: list[PaneEntry] = []
        for entry in self._entries:
            next_size_label = update_by_path.get(entry.path)
            if next_size_label is None or next_size_label == entry.size_label:
                next_entries.append(entry)
                continue
            next_entry = replace(entry, size_label=next_size_label)
            next_entries.append(next_entry)
            changed_rows.append((entry.path, next_entry))

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

        update_by_path = {update.path: update.entry for update in updates}
        changed_rows: list[tuple[str, PaneEntry]] = []
        next_entries: list[PaneEntry] = []
        for entry in self._entries:
            next_entry = update_by_path.get(entry.path)
            if next_entry is None or next_entry == entry:
                next_entries.append(entry)
                continue
            next_entries.append(next_entry)
            changed_rows.append((entry.path, next_entry))

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

    # -- Table building ---------------------------------------------------------

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

    # -- Row / cell helpers -----------------------------------------------------

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
            cls._render_cell(entry.selection_marker, entry),
            cls._render_cell(
                truncate_middle(build_entry_label(entry), column_widths["name"]),
                entry,
            ),
            cls._render_cell(entry.size_label, entry),
            cls._render_cell(entry.modified_label, entry),
        )

    # -- Column layout ----------------------------------------------------------

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

    # -- Style / rendering ------------------------------------------------------

    @classmethod
    def _entry_style(cls, entry: PaneEntry) -> str | None:
        if entry.cut:
            if entry.symlink:
                return cls.SYMLINK_CUT_STYLE
            if entry.kind == "dir":
                return cls.DIRECTORY_CUT_STYLE
            if entry.executable:
                return cls.EXECUTABLE_CUT_STYLE
            if entry.selected:
                return cls.SELECTED_CUT_STYLE
            return cls.CUT_STYLE
        if entry.symlink:
            if entry.selected:
                return cls.SYMLINK_SELECTED_STYLE
            return cls.SYMLINK_STYLE
        if entry.kind == "dir":
            if entry.selected:
                return cls.DIRECTORY_SELECTED_STYLE
            return cls.DIRECTORY_STYLE
        if entry.executable:
            if entry.selected:
                return cls.EXECUTABLE_SELECTED_STYLE
            return cls.EXECUTABLE_STYLE
        if entry.selected:
            return cls.SELECTED_STYLE
        return None

    @classmethod
    def _render_cell(cls, value: str, entry: PaneEntry) -> Text:
        style = cls._entry_style(entry)
        return Text(value) if style is None else Text(value, style=style)
