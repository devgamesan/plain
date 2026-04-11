from peneo.models import PaneEntry
from peneo.ui.panes import SidePane, build_entry_label, truncate_middle


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
