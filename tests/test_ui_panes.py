from unittest.mock import Mock

from rich.style import Style
from textual.widgets import DataTable

from zivo.models import CurrentSummaryState, PaneEntry
from zivo.ui.panes import (
    MainPane,
    _ft_resolve_style,
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
    """パス変更がある場合、全再構築すること"""
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

    assert result is True, "パス変更がある場合は全再構築"


def test_should_rebuild_rows_with_sort() -> None:
    """ソート時（同じパス集合でも順序が異なる）は全再構築が必要なこと"""
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

    assert result is True, "ソート時は全再構築が必要"


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

