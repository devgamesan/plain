from peneo.models import PaneEntry
from peneo.ui.panes import MainPane, SidePane, build_entry_label, truncate_middle


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


def test_side_pane_selected_directory_uses_background_highlight() -> None:
    entry = PaneEntry("docs", "dir", selected=True)

    rendered = SidePane._render_label(entry)

    assert rendered.style == "bold white on #5555FF"


# -- MainPane._entry_style ------------------------------------------------------


def test_entry_style_cut_symlink() -> None:
    entry = PaneEntry("link", "file", cut=True, symlink=True)
    assert MainPane._entry_style(entry) == MainPane.SYMLINK_CUT_STYLE


def test_entry_style_cut_directory() -> None:
    entry = PaneEntry("dir", "dir", cut=True)
    assert MainPane._entry_style(entry) == MainPane.DIRECTORY_CUT_STYLE


def test_entry_style_cut_executable() -> None:
    entry = PaneEntry("script.sh", "file", cut=True, executable=True)
    assert MainPane._entry_style(entry) == MainPane.EXECUTABLE_CUT_STYLE


def test_entry_style_cut_selected() -> None:
    entry = PaneEntry("file.txt", "file", cut=True, selected=True)
    assert MainPane._entry_style(entry) == MainPane.SELECTED_CUT_STYLE


def test_entry_style_cut_plain() -> None:
    entry = PaneEntry("file.txt", "file", cut=True)
    assert MainPane._entry_style(entry) == MainPane.CUT_STYLE


def test_entry_style_symlink_selected() -> None:
    entry = PaneEntry("link", "file", symlink=True, selected=True)
    assert MainPane._entry_style(entry) == MainPane.SYMLINK_SELECTED_STYLE


def test_entry_style_symlink() -> None:
    entry = PaneEntry("link", "file", symlink=True)
    assert MainPane._entry_style(entry) == MainPane.SYMLINK_STYLE


def test_entry_style_directory_selected() -> None:
    entry = PaneEntry("docs", "dir", selected=True)
    assert MainPane._entry_style(entry) == MainPane.DIRECTORY_SELECTED_STYLE


def test_entry_style_directory() -> None:
    entry = PaneEntry("docs", "dir")
    assert MainPane._entry_style(entry) == MainPane.DIRECTORY_STYLE


def test_entry_style_executable_selected() -> None:
    entry = PaneEntry("run.sh", "file", executable=True, selected=True)
    assert MainPane._entry_style(entry) == MainPane.EXECUTABLE_SELECTED_STYLE


def test_entry_style_executable() -> None:
    entry = PaneEntry("run.sh", "file", executable=True)
    assert MainPane._entry_style(entry) == MainPane.EXECUTABLE_STYLE


def test_entry_style_selected() -> None:
    entry = PaneEntry("file.txt", "file", selected=True)
    assert MainPane._entry_style(entry) == MainPane.SELECTED_STYLE


def test_entry_style_plain() -> None:
    entry = PaneEntry("file.txt", "file")
    assert MainPane._entry_style(entry) is None


# -- MainPane._render_cell ------------------------------------------------------


def test_render_cell_plain_entry() -> None:
    entry = PaneEntry("file.txt", "file")
    result = MainPane._render_cell("file.txt", entry)
    assert result.plain == "file.txt"
    assert not result.style


def test_render_cell_selected_entry() -> None:
    entry = PaneEntry("file.txt", "file", selected=True)
    result = MainPane._render_cell("file.txt", entry)
    assert result.plain == "file.txt"
    assert result.style == MainPane.SELECTED_STYLE


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
