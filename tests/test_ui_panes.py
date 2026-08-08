from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from rich.style import Style
from rich.text import Text
from textual.widgets import DataTable

from zivo.models import (
    ChildPaneViewState,
    CurrentPaneRowUpdate,
    CurrentPaneSizeUpdate,
    CurrentSummaryState,
    PaneEntry,
)
from zivo.ui.pane_rendering import _FileEntryLabelCache
from zivo.ui.panes import (
    ChildPane,
    MainPane,
    SidePane,
    _ft_resolve_style,
    _guess_preview_lexer,
    _render_file_label,
    _style_without_background,
    build_entry_label,
    truncate_middle,
)


def _style_map() -> dict[str, Style]:
    return {
        "ft-cut": Style.parse("dim"),
        "ft-directory": Style.parse("bold blue"),
        "ft-directory-cut": Style.parse("bold blue dim"),
        "ft-directory-sel": Style.parse("bold underline blue"),
        "ft-directory-sel-table": Style.parse("bold blue"),
        "ft-executable": Style.parse("bold green"),
        "ft-executable-cut": Style.parse("bold green dim"),
        "ft-executable-sel": Style.parse("bold green"),
        "ft-selected": Style.parse("bold green"),
        "ft-selected-cut": Style.parse("bold bright_black"),
        "ft-symlink": Style.parse("bold cyan"),
        "ft-symlink-cut": Style.parse("bold cyan dim"),
        "ft-symlink-sel": Style.parse("bold cyan"),
    }


def test_truncate_middle_keeps_text_when_width_is_sufficient() -> None:
    assert truncate_middle("README.md", 9) == "README.md"


def test_truncate_middle_uses_middle_marker_for_long_name() -> None:
    rendered = truncate_middle("very-long-directory-name", 10)

    assert rendered == "very-~name"
    assert "~" in rendered


def test_truncate_middle_preserves_file_extension_when_possible() -> None:
    assert truncate_middle("reducer_common.py", 11) == "reducer~.py"


def test_truncate_middle_handles_extremely_narrow_widths() -> None:
    assert truncate_middle("README.md", 1) == "~"
    assert truncate_middle("README.md", 2) == "~d"


def test_build_entry_label_truncates_full_name_detail_string() -> None:
    entry = PaneEntry("archive.tar.gz", "file", name_detail="2.1KiB")

    rendered = truncate_middle(build_entry_label(entry), 15)

    assert "~" in rendered
    assert rendered.endswith("1KiB)")


def test_pane_entry_supports_executable_field() -> None:
    """PaneEntry が executable フィールドをサポートすること"""
    entry = PaneEntry("script.sh", "file", executable=True)

    assert entry.executable is True
    assert entry.kind == "file"


def test_pane_entry_defaults_executable_to_false() -> None:
    """PaneEntry の executable がデフォルトで False であること"""
    entry = PaneEntry("README.md", "file")

    assert entry.executable is False


def test_child_pane_renders_image_preview_as_ansi() -> None:
    renderable = ChildPane._render_preview(
        ChildPaneViewState(
            title="Preview: image.png",
            preview_path="/tmp/image.png",
            preview_content="\x1b[31m@@\x1b[0m\n",
            preview_kind="image",
        ),
        40,
    )

    assert isinstance(renderable, Text)
    assert renderable.plain == "@@\n"
    assert renderable.no_wrap is True


def test_child_pane_image_preview_resize_schedules_chafa_without_loading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pane = ChildPane(
        ChildPaneViewState(
            title="Preview: image.png",
            preview_path="/tmp/image.png",
            preview_content="seed\n",
            preview_kind="image",
        )
    )
    widget = SimpleNamespace(
        size=SimpleNamespace(width=42),
        updates=[],
        update=lambda renderable: widget.updates.append(renderable),
    )
    timers: list[SimpleNamespace] = []

    def fake_set_timer(
        delay: float,
        callback: object,
        *,
        name: str | None = None,
        pause: bool = False,
    ) -> SimpleNamespace:
        timer = SimpleNamespace(
            delay=delay,
            callback=callback,
            name=name,
            pause=pause,
            stop=Mock(),
        )
        timers.append(timer)
        return timer

    monkeypatch.setattr(pane, "_preview_widget", lambda: widget)
    monkeypatch.setattr(pane, "set_timer", fake_set_timer)
    monkeypatch.setattr(
        pane,
        "run_worker",
        Mock(side_effect=AssertionError("worker should wait for debounce")),
    )

    assert pane._refresh_rendered_content(force=True) is True

    assert len(timers) == 1
    assert timers[0].name == "chafa-resize-debounce:1"
    assert pane._last_chafa_width == 0
    assert widget.updates[-1].plain == "seed\n"


def test_child_pane_image_preview_resize_ignores_stale_chafa_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pane = ChildPane(
        ChildPaneViewState(
            title="Preview: image.png",
            preview_path="/tmp/image.png",
            preview_content="seed\n",
            preview_kind="image",
        )
    )
    widget = SimpleNamespace(
        updates=[],
        update=lambda renderable: widget.updates.append(renderable),
    )
    timers: list[SimpleNamespace] = []

    def fake_set_timer(
        delay: float,
        callback: object,
        *,
        name: str | None = None,
        pause: bool = False,
    ) -> SimpleNamespace:
        timer = SimpleNamespace(
            delay=delay,
            callback=callback,
            name=name,
            pause=pause,
            stop=Mock(),
        )
        timers.append(timer)
        return timer

    monkeypatch.setattr(pane, "_preview_widget", lambda: widget)
    monkeypatch.setattr(pane, "set_timer", fake_set_timer)

    pane._schedule_chafa_resize_preview("/tmp/image.png", 40, "symbols")
    pane._schedule_chafa_resize_preview("/tmp/image.png", 60, "symbols")
    pane._complete_chafa_resize_request(
        1,
        "/tmp/image.png",
        40,
        "symbols",
        "stale\n",
    )
    pane._complete_chafa_resize_request(
        2,
        "/tmp/image.png",
        60,
        "symbols",
        "fresh\n",
    )

    assert timers[0].stop.called is True
    assert pane._chafa_cached_content == "fresh\n"
    assert pane._last_chafa_width == 60
    assert widget.updates[-1].plain == "fresh\n"


def test_child_pane_reuses_image_preview_loader_for_resize_workers() -> None:
    class StubImagePreviewLoader:
        def __init__(self) -> None:
            self.calls: list[tuple[str, int, str, int]] = []

        def load_preview(
            self,
            path,
            *,
            preview_columns: int,
            image_preview_format: str = "symbols",
        ):
            self.calls.append(
                (str(path), preview_columns, image_preview_format, id(self))
            )
            return SimpleNamespace(content=f"{preview_columns}:{image_preview_format}\n")

    loader = StubImagePreviewLoader()
    pane = ChildPane(
        ChildPaneViewState(
            title="Preview: image.png",
            preview_path="/tmp/image.png",
            preview_content="seed\n",
            preview_kind="image",
        ),
        image_preview_loader=loader,
    )
    pane.run_worker = lambda worker, **_kwargs: worker()  # type: ignore[method-assign]

    pane._chafa_resize_request_id = 1
    pane._pending_chafa_resize_key = ("/tmp/image.png", 40, "symbols")
    pane._start_chafa_resize_worker(1, "/tmp/image.png", 40, "symbols")
    pane._pending_chafa_resize_key = ("/tmp/image.png", 60, "symbols")
    pane._start_chafa_resize_worker(1, "/tmp/image.png", 60, "symbols")

    assert loader.calls == [
        ("/tmp/image.png", 40, "symbols", id(loader)),
        ("/tmp/image.png", 60, "symbols", id(loader)),
    ]


def test_side_pane_selected_directory_uses_text_only_highlight() -> None:
    styles = _style_map()
    entry = PaneEntry("docs", "dir", selected=True)

    rendered = _render_file_label(
        entry,
        0,
        styles,
        selected_directory_style="ft-directory-sel",
        selected_cut_style="ft-cut",
    )

    assert rendered.style == styles["ft-directory-sel"]


# -- File type style resolution -------------------------------------------------


def test_entry_style_cut_symlink() -> None:
    styles = _style_map()
    entry = PaneEntry("link", "file", cut=True, symlink=True)
    assert (
        _ft_resolve_style(
            entry,
            styles,
            selected_directory_style="ft-directory-sel-table",
            selected_cut_style="ft-selected-cut",
        )
        == styles["ft-symlink-cut"]
    )


def test_entry_style_cut_directory() -> None:
    styles = _style_map()
    entry = PaneEntry("dir", "dir", cut=True)
    assert (
        _ft_resolve_style(
            entry,
            styles,
            selected_directory_style="ft-directory-sel-table",
            selected_cut_style="ft-selected-cut",
        )
        == styles["ft-directory-cut"]
    )


def test_entry_style_cut_executable() -> None:
    styles = _style_map()
    entry = PaneEntry("script.sh", "file", cut=True, executable=True)
    assert (
        _ft_resolve_style(
            entry,
            styles,
            selected_directory_style="ft-directory-sel-table",
            selected_cut_style="ft-selected-cut",
        )
        == styles["ft-executable-cut"]
    )


def test_entry_style_cut_selected() -> None:
    styles = _style_map()
    entry = PaneEntry("file.txt", "file", cut=True, selected=True)
    assert (
        _ft_resolve_style(
            entry,
            styles,
            selected_directory_style="ft-directory-sel-table",
            selected_cut_style="ft-selected-cut",
        )
        == styles["ft-selected-cut"]
    )


def test_entry_style_cut_plain() -> None:
    styles = _style_map()
    entry = PaneEntry("file.txt", "file", cut=True)
    assert (
        _ft_resolve_style(
            entry,
            styles,
            selected_directory_style="ft-directory-sel-table",
            selected_cut_style="ft-selected-cut",
        )
        == styles["ft-cut"]
    )


def test_entry_style_symlink_selected() -> None:
    styles = _style_map()
    entry = PaneEntry("link", "file", symlink=True, selected=True)
    assert (
        _ft_resolve_style(
            entry,
            styles,
            selected_directory_style="ft-directory-sel-table",
            selected_cut_style="ft-selected-cut",
        )
        == styles["ft-symlink-sel"]
    )


def test_entry_style_symlink() -> None:
    styles = _style_map()
    entry = PaneEntry("link", "file", symlink=True)
    assert (
        _ft_resolve_style(
            entry,
            styles,
            selected_directory_style="ft-directory-sel-table",
            selected_cut_style="ft-selected-cut",
        )
        == styles["ft-symlink"]
    )


def test_entry_style_directory_selected() -> None:
    styles = _style_map()
    entry = PaneEntry("docs", "dir", selected=True)
    assert (
        _ft_resolve_style(
            entry,
            styles,
            selected_directory_style="ft-directory-sel-table",
            selected_cut_style="ft-selected-cut",
        )
        == styles["ft-directory-sel-table"]
    )


def test_entry_style_directory() -> None:
    styles = _style_map()
    entry = PaneEntry("docs", "dir")
    assert (
        _ft_resolve_style(
            entry,
            styles,
            selected_directory_style="ft-directory-sel-table",
            selected_cut_style="ft-selected-cut",
        )
        == styles["ft-directory"]
    )


def test_entry_style_executable_selected() -> None:
    styles = _style_map()
    entry = PaneEntry("run.sh", "file", executable=True, selected=True)
    assert (
        _ft_resolve_style(
            entry,
            styles,
            selected_directory_style="ft-directory-sel-table",
            selected_cut_style="ft-selected-cut",
        )
        == styles["ft-executable-sel"]
    )


def test_entry_style_executable() -> None:
    styles = _style_map()
    entry = PaneEntry("run.sh", "file", executable=True)
    assert (
        _ft_resolve_style(
            entry,
            styles,
            selected_directory_style="ft-directory-sel-table",
            selected_cut_style="ft-selected-cut",
        )
        == styles["ft-executable"]
    )


def test_entry_style_selected() -> None:
    styles = _style_map()
    entry = PaneEntry("file.txt", "file", selected=True)
    assert (
        _ft_resolve_style(
            entry,
            styles,
            selected_directory_style="ft-directory-sel-table",
            selected_cut_style="ft-selected-cut",
        )
        == styles["ft-selected"]
    )


def test_entry_style_plain() -> None:
    styles = _style_map()
    entry = PaneEntry("file.txt", "file")
    assert (
        _ft_resolve_style(
            entry,
            styles,
            selected_directory_style="ft-directory-sel-table",
            selected_cut_style="ft-selected-cut",
        )
        is None
    )


# -- Label rendering ------------------------------------------------------------


def test_render_cell_plain_entry() -> None:
    styles = _style_map()
    entry = PaneEntry("file.txt", "file")
    result = _render_file_label(
        entry,
        0,
        styles,
        selected_directory_style="ft-directory-sel-table",
        selected_cut_style="ft-selected-cut",
    )
    assert result.plain == "file.txt"
    assert not result.style


def test_render_cell_selected_entry() -> None:
    styles = _style_map()
    entry = PaneEntry("file.txt", "file", selected=True)
    result = _render_file_label(
        entry,
        0,
        styles,
        selected_directory_style="ft-directory-sel-table",
        selected_cut_style="ft-selected-cut",
    )
    assert result.plain == "file.txt"
    assert result.style == styles["ft-selected"]


def test_file_entry_label_cache_updates_only_changed_hover_rows(monkeypatch) -> None:
    styles = _style_map()
    entries = tuple(
        PaneEntry(f"file-{index}.txt", "file", path=f"/path/file-{index}.txt")
        for index in range(100)
    )
    cache = _FileEntryLabelCache()
    cache.rebuild(
        entries,
        40,
        styles,
        selected_directory_style="ft-directory-sel",
        selected_cut_style="ft-cut",
    )

    calls: list[str] = []

    def counting_render_file_label(
        entry,
        render_width,
        styles,
        *,
        selected_directory_style,
        selected_cut_style,
        hovered_path=None,
    ):
        calls.append(entry.path)
        return _render_file_label(
            entry,
            render_width,
            styles,
            selected_directory_style=selected_directory_style,
            selected_cut_style=selected_cut_style,
            hovered_path=hovered_path,
        )

    monkeypatch.setattr(
        "zivo.ui.pane_rendering._render_file_label",
        counting_render_file_label,
    )

    rendered = cache.update_hover(
        None,
        "/path/file-10.txt",
        styles,
        selected_directory_style="ft-directory-sel",
        selected_cut_style="ft-cut",
    )

    assert rendered is not None
    assert calls == ["/path/file-10.txt"]

    calls.clear()
    rendered = cache.update_hover(
        "/path/file-10.txt",
        "/path/file-11.txt",
        styles,
        selected_directory_style="ft-directory-sel",
        selected_cut_style="ft-cut",
    )

    assert rendered is not None
    assert calls == ["/path/file-10.txt", "/path/file-11.txt"]


def test_side_pane_mouse_move_without_entry_meta_does_not_refresh() -> None:
    pane = SidePane(
        "Parent",
        (PaneEntry("file.txt", "file", path="/path/file.txt"),),
        id="parent-pane",
    )
    pane._refresh_hovered_labels = Mock(return_value=True)  # type: ignore[method-assign]
    pane._refresh_rendered_labels = Mock()  # type: ignore[method-assign]
    event = SimpleNamespace(style=SimpleNamespace(meta={}))

    pane.on_mouse_move(event)

    pane._refresh_hovered_labels.assert_not_called()
    pane._refresh_rendered_labels.assert_not_called()


def test_style_without_background_keeps_foreground_and_text_attributes() -> None:
    style = Style.parse("bold blue on black")

    stripped = _style_without_background(style)

    assert stripped is not None
    assert stripped.color == style.color
    assert stripped.bgcolor is None
    assert stripped.bold is True


# -- MainPane._shrink_fixed_columns ---------------------------------------------


def test_shrink_fixed_columns_enough_space() -> None:
    result = MainPane._shrink_fixed_columns(100)
    assert result == dict(MainPane.FIXED_COLUMN_PREFERRED_WIDTHS)


def test_shrink_fixed_columns_tight_space() -> None:
    result = MainPane._shrink_fixed_columns(20)
    assert result["sel"] >= MainPane.FIXED_COLUMN_MIN_WIDTHS["sel"]
    assert sum(result.values()) + MainPane.NAME_MIN_WIDTH <= 20


def test_shrink_fixed_columns_extremely_tight() -> None:
    result = MainPane._shrink_fixed_columns(5)
    assert result == dict(MainPane.FIXED_COLUMN_MIN_WIDTHS)


# -- MainPane._should_rebuild_rows ------------------------------------------------


def test_should_rebuild_rows_with_same_paths() -> None:
    """同じパス集合の場合、差分更新のみ行うこと"""
    summary = CurrentSummaryState(item_count=3, selected_count=0, sort_label="Name")
    pane = MainPane(title="Test", entries=[], summary=summary)
    table = Mock(spec=DataTable)
    table.size.width = 80
    pane._last_table_width = 80

    previous_entries = (
        PaneEntry("a.txt", "file", path="/path/a.txt"),
        PaneEntry("b.txt", "file", path="/path/b.txt"),
        PaneEntry("c.txt", "file", path="/path/c.txt"),
    )
    next_entries = (
        PaneEntry("a.txt", "file", path="/path/a.txt"),
        PaneEntry("b.txt", "file", path="/path/b.txt"),
        PaneEntry("c.txt", "file", path="/path/c.txt"),
    )

    result = pane._should_rebuild_rows(table, previous_entries, next_entries)

    assert result is False, "同じパス集合の場合は差分更新のみ"


def test_should_rebuild_rows_with_path_changes() -> None:
    """パス変更があっても同じ行数なら差分更新だけ行うこと."""
    summary = CurrentSummaryState(item_count=3, selected_count=0, sort_label="Name")
    pane = MainPane(title="Test", entries=[], summary=summary)
    table = Mock(spec=DataTable)
    table.size.width = 80
    pane._last_table_width = 80

    previous_entries = (
        PaneEntry("a.txt", "file", path="/path/a.txt"),
        PaneEntry("b.txt", "file", path="/path/b.txt"),
        PaneEntry("c.txt", "file", path="/path/c.txt"),
    )
    next_entries = (
        PaneEntry("a.txt", "file", path="/path/a.txt"),
        PaneEntry("d.txt", "file", path="/path/d.txt"),  # 異なるパス
        PaneEntry("c.txt", "file", path="/path/c.txt"),
    )

    result = pane._should_rebuild_rows(table, previous_entries, next_entries)

    assert result is False, "同じ行数なら差分更新で十分"


def test_should_rebuild_rows_with_sort() -> None:
    """ソートで順序が変わっても同じ行数なら差分更新だけ行うこと."""
    summary = CurrentSummaryState(item_count=3, selected_count=0, sort_label="Name")
    pane = MainPane(title="Test", entries=[], summary=summary)
    table = Mock(spec=DataTable)
    table.size.width = 80
    pane._last_table_width = 80

    previous_entries = (
        PaneEntry("c.txt", "file", path="/path/c.txt"),
        PaneEntry("a.txt", "file", path="/path/a.txt"),
        PaneEntry("b.txt", "file", path="/path/b.txt"),
    )
    next_entries = (
        PaneEntry("a.txt", "file", path="/path/a.txt"),
        PaneEntry("b.txt", "file", path="/path/b.txt"),
        PaneEntry("c.txt", "file", path="/path/c.txt"),
    )

    result = pane._should_rebuild_rows(table, previous_entries, next_entries)

    assert result is False, "ソート時も差分更新で十分"


def test_should_rebuild_rows_with_width_change() -> None:
    """テーブル幅変更時、全再構築すること"""
    summary = CurrentSummaryState(item_count=2, selected_count=0, sort_label="Name")
    pane = MainPane(title="Test", entries=[], summary=summary)
    table = Mock(spec=DataTable)
    table.size.width = 100  # 異なる幅
    pane._last_table_width = 80

    previous_entries = (
        PaneEntry("a.txt", "file", path="/path/a.txt"),
        PaneEntry("b.txt", "file", path="/path/b.txt"),
    )
    next_entries = (
        PaneEntry("a.txt", "file", path="/path/a.txt"),
        PaneEntry("b.txt", "file", path="/path/b.txt"),
    )

    result = pane._should_rebuild_rows(table, previous_entries, next_entries)

    assert result is True, "テーブル幅変更時は全再構築"


def test_should_rebuild_rows_with_count_change() -> None:
    """エントリ数変更時、全再構築すること"""
    summary = CurrentSummaryState(item_count=2, selected_count=0, sort_label="Name")
    pane = MainPane(title="Test", entries=[], summary=summary)
    table = Mock(spec=DataTable)
    table.size.width = 80
    pane._last_table_width = 80

    previous_entries = (
        PaneEntry("a.txt", "file", path="/path/a.txt"),
        PaneEntry("b.txt", "file", path="/path/b.txt"),
    )
    next_entries = (
        PaneEntry("a.txt", "file", path="/path/a.txt"),
        PaneEntry("b.txt", "file", path="/path/b.txt"),
        PaneEntry("c.txt", "file", path="/path/c.txt"),  # 追加
    )

    result = pane._should_rebuild_rows(table, previous_entries, next_entries)

    assert result is True, "エントリ数変更時は全再構築"


def test_apply_row_updates_updates_slot_key_for_visible_row() -> None:
    summary = CurrentSummaryState(item_count=2, selected_count=0, sort_label="Name")
    entries = (
        PaneEntry("a.txt", "file", path="/path/a.txt"),
        PaneEntry("b.txt", "file", path="/path/b.txt"),
    )
    pane = MainPane(title="Test", entries=entries, summary=summary)
    table = Mock(spec=DataTable)
    table.size.width = 80
    table.cell_padding = 1
    pane.query_one = Mock(return_value=table)

    pane.apply_row_updates(
        (
            CurrentPaneRowUpdate(
                path="/path/b.txt",
                entry=PaneEntry("renamed.txt", "file", path="/path/b.txt"),
                row_index=1,
            ),
        )
    )

    assert pane._entries[1].name == "renamed.txt"
    assert table.update_cell.call_count == 4
    assert table.update_cell.call_args_list[0].args[0] == "__slot__:1"


def test_apply_size_updates_updates_only_target_slot() -> None:
    summary = CurrentSummaryState(item_count=2, selected_count=0, sort_label="Name")
    entries = (
        PaneEntry("a.txt", "file", path="/path/a.txt", size_label="1 B"),
        PaneEntry("b.txt", "file", path="/path/b.txt", size_label="2 B"),
    )
    pane = MainPane(title="Test", entries=entries, summary=summary)
    table = Mock(spec=DataTable)
    pane.query_one = Mock(return_value=table)

    pane.apply_size_updates(
        (
            CurrentPaneSizeUpdate(
                path="/path/b.txt",
                size_label="3 B",
                row_index=1,
            ),
        )
    )

    assert pane._entries[0] is entries[0]
    assert pane._entries[1].size_label == "3 B"
    table.update_cell.assert_called_once()
    assert table.update_cell.call_args.args[0] == "__slot__:1"
    assert table.update_cell.call_args.args[1] == "size"


def test_apply_size_updates_resolves_stale_row_index_by_path_index() -> None:
    summary = CurrentSummaryState(item_count=3, selected_count=0, sort_label="Name")
    entries = (
        PaneEntry("a.txt", "file", path="/path/a.txt", size_label="1 B"),
        PaneEntry("b.txt", "file", path="/path/b.txt", size_label="2 B"),
        PaneEntry("c.txt", "file", path="/path/c.txt", size_label="3 B"),
    )
    pane = MainPane(title="Test", entries=entries, summary=summary)
    table = Mock(spec=DataTable)
    pane.query_one = Mock(return_value=table)

    pane.apply_size_updates(
        (
            CurrentPaneSizeUpdate(
                path="/path/c.txt",
                size_label="4 B",
                row_index=0,
            ),
        )
    )

    assert pane._entries[2].size_label == "4 B"
    table.update_cell.assert_called_once()
    assert table.update_cell.call_args.args[0] == "__slot__:2"


def test_apply_size_updates_path_fallback_keeps_first_duplicate_match() -> None:
    summary = CurrentSummaryState(item_count=3, selected_count=0, sort_label="Name")
    entries = (
        PaneEntry("first.txt", "file", path="/path/shared.txt", size_label="1 B"),
        PaneEntry("other.txt", "file", path="/path/other.txt", size_label="2 B"),
        PaneEntry("second.txt", "file", path="/path/shared.txt", size_label="3 B"),
    )
    pane = MainPane(title="Test", entries=entries, summary=summary)
    table = Mock(spec=DataTable)
    pane.query_one = Mock(return_value=table)

    pane.apply_size_updates(
        (
            CurrentPaneSizeUpdate(
                path="/path/shared.txt",
                size_label="4 B",
                row_index=1,
            ),
        )
    )

    assert pane._entries[0].size_label == "4 B"
    assert pane._entries[2].size_label == "3 B"
    table.update_cell.assert_called_once()
    assert table.update_cell.call_args.args[0] == "__slot__:0"


def test_set_entries_refreshes_path_row_index() -> None:
    summary = CurrentSummaryState(item_count=2, selected_count=0, sort_label="Name")
    entries = (
        PaneEntry("a.txt", "file", path="/path/a.txt", size_label="1 B"),
        PaneEntry("b.txt", "file", path="/path/b.txt", size_label="2 B"),
    )
    next_entries = (
        PaneEntry("c.txt", "file", path="/path/c.txt", size_label="3 B"),
        PaneEntry("d.txt", "file", path="/path/d.txt", size_label="4 B"),
    )
    pane = MainPane(title="Test", entries=entries, summary=summary)
    table = Mock(spec=DataTable)
    table.size.width = 80
    table.cell_padding = 1
    pane._last_table_width = 80
    pane.query_one = Mock(return_value=table)

    pane.set_entries(next_entries)
    table.reset_mock()

    pane.apply_size_updates(
        (
            CurrentPaneSizeUpdate(
                path="/path/a.txt",
                size_label="9 B",
                row_index=1,
            ),
            CurrentPaneSizeUpdate(
                path="/path/d.txt",
                size_label="5 B",
                row_index=0,
            ),
        )
    )

    assert pane._entries[0].size_label == "3 B"
    assert pane._entries[1].size_label == "5 B"
    table.update_cell.assert_called_once()
    assert table.update_cell.call_args.args[0] == "__slot__:1"


def test_set_entries_clears_stale_hover_cursor() -> None:
    summary = CurrentSummaryState(item_count=2, selected_count=0, sort_label="Name")
    entries = (
        PaneEntry("a.txt", "file", path="/path/a.txt"),
        PaneEntry("b.txt", "file", path="/path/b.txt"),
    )
    next_entries = (
        PaneEntry("c.txt", "file", path="/path/c.txt"),
        PaneEntry("d.txt", "file", path="/path/d.txt"),
    )
    pane = MainPane(title="Test", entries=entries, summary=summary)
    table = Mock(spec=DataTable)
    table.size.width = 80
    table.cell_padding = 1
    pane._last_table_width = 80
    pane.query_one = Mock(return_value=table)

    pane.set_entries(next_entries, cursor_index=0)

    table._set_hover_cursor.assert_called_with(False)


def test_child_pane_refresh_rendered_content_skips_duplicate_preview_render(
    monkeypatch,
) -> None:
    pane = ChildPane(
        ChildPaneViewState(
            title="Preview",
            preview_path="/tmp/example.py",
            preview_content="print('zivo')\n",
        ),
        id="child-pane",
    )
    preview_widget = Mock()
    preview_widget.size = SimpleNamespace(width=48)
    preview_widget.update = Mock()
    pane._preview_widget = lambda: preview_widget  # type: ignore[method-assign]

    _guess_preview_lexer.cache_clear()
    _mock_render = staticmethod(
        lambda state, render_width, chafa_override=None: f"{state.preview_path}:{render_width}"
    )
    monkeypatch.setattr(ChildPane, "_render_preview", _mock_render)

    assert pane._refresh_rendered_content() is True
    assert pane._refresh_rendered_content() is True
    assert preview_widget.update.call_count == 1


@pytest.mark.asyncio
async def test_child_pane_clears_kitty_preview_when_leaving_preview() -> None:
    pane = ChildPane(
        ChildPaneViewState(
            title="Preview",
            preview_path="/tmp/image.png",
            preview_content="\033_Gf=100;AAAA\033\\",
            preview_kind="kitty",
        ),
        id="child-pane",
    )
    list_widget = SimpleNamespace(display=False)
    scroll_widget = SimpleNamespace(display=True, scroll_home=Mock())
    writer = Mock()
    pane._list_widget = lambda: list_widget  # type: ignore[method-assign]
    pane._preview_scroll_widget = lambda: scroll_widget  # type: ignore[method-assign]
    pane._refresh_rendered_content = Mock(return_value=True)  # type: ignore[method-assign]
    pane._write_terminal_content = writer  # type: ignore[method-assign]
    pane.call_after_refresh = lambda callback: callback()  # type: ignore[method-assign]

    await pane.set_state(ChildPaneViewState(title="Preview"))

    writer.assert_called_once_with("\033_Ga=d,d=A\033\\")
    assert list_widget.display is True
    assert scroll_widget.display is False


@pytest.mark.asyncio
async def test_child_pane_keeps_current_kitty_preview_without_extra_clear() -> None:
    state = ChildPaneViewState(
        title="Preview",
        preview_path="/tmp/image.png",
        preview_content="\033_Gf=100;AAAA\033\\",
        preview_kind="kitty",
    )
    pane = ChildPane(state, id="child-pane")
    list_widget = SimpleNamespace(display=False)
    scroll_widget = SimpleNamespace(display=True, scroll_home=Mock())
    writer = Mock()
    pane._list_widget = lambda: list_widget  # type: ignore[method-assign]
    pane._preview_scroll_widget = lambda: scroll_widget  # type: ignore[method-assign]
    pane._refresh_rendered_content = Mock(return_value=True)  # type: ignore[method-assign]
    pane._write_terminal_content = writer  # type: ignore[method-assign]
    pane.call_after_refresh = lambda callback: callback()  # type: ignore[method-assign]

    await pane.set_state(
        ChildPaneViewState(
            title="Preview",
            preview_path="/tmp/image.png",
            preview_content="\033_Gf=100;AAAA\033\\",
            preview_kind="kitty",
            preview_start_line=1,
        )
    )

    writer.assert_not_called()


def test_child_pane_clears_kitty_preview_on_unmount() -> None:
    pane = ChildPane(
        ChildPaneViewState(
            title="Preview",
            preview_path="/tmp/image.png",
            preview_content="\033_Gf=100;AAAA\033\\",
            preview_kind="kitty",
        ),
        id="child-pane",
    )
    writer = Mock()
    pane._write_terminal_content = writer  # type: ignore[method-assign]

    pane.on_unmount()

    writer.assert_called_once_with("\033_Ga=d,d=A\033\\")


def test_child_pane_writes_new_kitty_content_when_path_changes_same_width(
    monkeypatch,
) -> None:
    pane = ChildPane(
        ChildPaneViewState(
            title="Preview",
            preview_path="/tmp/new.png",
            preview_content="\033_Gf=100;NEW\033\\",
            preview_kind="kitty",
        ),
        id="child-pane",
    )
    scroll_widget = SimpleNamespace(
        region=SimpleNamespace(x=4, y=2),
        size=SimpleNamespace(width=42),
    )
    writer = Mock()
    pane._preview_scroll_widget = lambda: scroll_widget  # type: ignore[method-assign]
    pane._write_terminal_content = writer  # type: ignore[method-assign]
    object.__setattr__(pane, "_last_kitty_path", "/tmp/old.png")
    object.__setattr__(pane, "_last_kitty_width", 40)
    object.__setattr__(pane, "_kitty_cached", "\033_Gf=100;OLD\033\\")
    monkeypatch.setattr(
        "zivo.services.previews.core.resolve_image_preview_format",
        lambda mode: "kitty",
    )

    pane._write_kitty_content("\033_Gf=100;NEW\033\\")

    writer.assert_called_once()
    assert "NEW" in writer.call_args.args[0]
    assert "OLD" not in writer.call_args.args[0]
