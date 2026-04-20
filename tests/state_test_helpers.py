from collections.abc import Iterable
from dataclasses import replace
from pathlib import Path

from zivo.state import reduce_app_state
from zivo.state.models import DirectoryEntryState, PaneState


def reduce_state(state, action):
    return reduce_app_state(state, action).state


def entry(
    path: str,
    kind: str = "file",
    *,
    name: str | None = None,
    hidden: bool = False,
    size_bytes: int | None = None,
    modified_at=None,
) -> DirectoryEntryState:
    return DirectoryEntryState(
        path=path,
        name=name or Path(path).name,
        kind=kind,
        size_bytes=size_bytes,
        modified_at=modified_at,
        hidden=hidden,
    )


def pane(
    directory_path: str,
    entries: Iterable[DirectoryEntryState],
    *,
    cursor_path: str | None = None,
    selected_paths: Iterable[str] = (),
) -> PaneState:
    entry_list = tuple(entries)
    return PaneState(
        directory_path=directory_path,
        entries=entry_list,
        cursor_path=cursor_path,
        selected_paths=frozenset(selected_paths),
    )


def replace_pane(state, pane_name: str, **changes):
    current_pane = getattr(state, pane_name)
    return replace(state, **{pane_name: replace(current_pane, **changes)})
