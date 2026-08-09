from dataclasses import replace
from pathlib import Path

from tests.state_test_helpers import entry, pane, reduce_state
from zivo.models import BulkRenameTarget
from zivo.services import LiveBulkRenameService
from zivo.state import build_initial_app_state, dispatch_key_input, reduce_app_state
from zivo.state.actions import (
    ApplyBulkRename,
    BeginBulkRename,
    BulkRenameCompleted,
    CycleBulkRenameField,
)
from zivo.state.effects import LoadBrowserSnapshotEffect, RunBulkRenameEffect


def _state_for_directory(directory: Path):
    paths = tuple(directory / name for name in ("a.txt", "b.txt"))
    return replace(
        build_initial_app_state(),
        current_path=str(directory),
        current_pane=pane(
            str(directory),
            (entry(str(paths[0])), entry(str(paths[1]))),
            cursor_path=str(paths[0]),
            selected_paths=(str(paths[0]), str(paths[1])),
        ),
    )


def test_bulk_rename_reducer_emits_effect_and_maps_selection(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("A")
    (tmp_path / "b.txt").write_text("B")
    state = _state_for_directory(tmp_path)
    targets = tuple(
        BulkRenameTarget(str(tmp_path / old), new)
        for old, new in (("a.txt", "c.txt"), ("b.txt", "d.txt"))
    )

    state = reduce_state(
        state,
        BeginBulkRename(parent_dir=str(tmp_path), targets=targets),
    )
    assert state.bulk_rename is not None
    assert state.ui_mode == "BULK_RENAME"
    assert state.bulk_rename.active_field == "find"
    state = replace(state, bulk_rename=replace(state.bulk_rename, active_field="apply"))
    applied = reduce_app_state(state, ApplyBulkRename())
    assert isinstance(applied.effects[0], RunBulkRenameEffect)

    request = applied.effects[0].request
    result = LiveBulkRenameService().execute(request)
    completed = reduce_app_state(
        applied.state,
        BulkRenameCompleted(request_id=applied.state.pending_bulk_rename_request_id, result=result),
    )

    assert completed.state.ui_mode == "BROWSING"
    assert completed.state.bulk_rename is None
    assert completed.state.current_pane.selected_paths == frozenset(
        {str(tmp_path / "c.txt"), str(tmp_path / "d.txt")}
    )
    assert completed.state.undo_stack[-1].kind == "bulk_rename"
    assert isinstance(completed.effects[0], LoadBrowserSnapshotEffect)


def test_bulk_rename_starts_at_find_and_tabs_to_replace(tmp_path: Path) -> None:
    state = _state_for_directory(tmp_path)
    targets = tuple(
        BulkRenameTarget(str(tmp_path / old), old)
        for old in ("a.txt", "b.txt")
    )

    state = reduce_state(
        state,
        BeginBulkRename(parent_dir=str(tmp_path), targets=targets),
    )

    actions = dispatch_key_input(state, key="tab")

    assert actions[-1] == CycleBulkRenameField(1)
    state = reduce_state(state, actions[-1])
    assert state.bulk_rename is not None
    assert state.bulk_rename.active_field == "replace"
