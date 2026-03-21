"""Display-only data used by the initial three-pane shell."""

from dataclasses import dataclass
from typing import Literal

EntryKind = Literal["dir", "file"]


@dataclass(frozen=True)
class PaneEntry:
    """A single row rendered in one of the directory panes."""

    name: str
    kind: EntryKind
    size_label: str = "-"
    modified_label: str = "-"

    @property
    def kind_label(self) -> str:
        """Return the short label shown in the center table."""
        return "DIR" if self.kind == "dir" else "FILE"


@dataclass(frozen=True)
class StatusBarState:
    """Summary values displayed in the bottom status bar."""

    path: str
    item_count: int
    selected_count: int
    sort_label: str
    filter_label: str


@dataclass(frozen=True)
class ThreePaneShellData:
    """Complete display state for the static shell UI."""

    parent_entries: tuple[PaneEntry, ...]
    current_entries: tuple[PaneEntry, ...]
    child_entries: tuple[PaneEntry, ...]
    status: StatusBarState


def build_dummy_shell_data() -> ThreePaneShellData:
    """Return static data for the initial three-pane shell."""
    current_entries = (
        PaneEntry("docs", "dir", "-", "2026-03-21 09:10"),
        PaneEntry("src", "dir", "-", "2026-03-20 19:42"),
        PaneEntry("tests", "dir", "-", "2026-03-20 19:42"),
        PaneEntry("README.md", "file", "2.1 KB", "2026-03-21 08:55"),
        PaneEntry("pyproject.toml", "file", "712 B", "2026-03-20 18:11"),
    )

    return ThreePaneShellData(
        parent_entries=(
            PaneEntry("develop", "dir"),
            PaneEntry("downloads", "dir"),
            PaneEntry("notes.txt", "file"),
        ),
        current_entries=current_entries,
        child_entries=(
            PaneEntry("spec_mvp.md", "file"),
            PaneEntry("notes.md", "file"),
            PaneEntry("wireframes", "dir"),
        ),
        status=StatusBarState(
            path="/home/tadashi/develop/plain",
            item_count=len(current_entries),
            selected_count=0,
            sort_label="name asc",
            filter_label="none",
        ),
    )
