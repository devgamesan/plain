from peneo.models import PaneEntry
from peneo.ui.panes import build_entry_label, truncate_middle


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
    entry = PaneEntry("archive.tar.gz", "file", name_detail="2.1 KB")

    rendered = truncate_middle(build_entry_label(entry), 15)

    assert "~" in rendered
    assert rendered.endswith("1 KB)")
