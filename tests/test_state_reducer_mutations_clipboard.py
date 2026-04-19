from dataclasses import replace
from pathlib import Path

from tests.test_state_reducer import _reduce_state
from zivo.models import (
    PasteAppliedChange,
    PasteConflict,
    PasteRequest,
    PasteSummary,
    UndoDeletePathStep,
    UndoEntry,
    UndoMovePathStep,
)
from zivo.state import (
    CancelPasteConflict,
    ClipboardPasteCompleted,
    ClipboardPasteFailed,
    ClipboardPasteNeedsResolution,
    CopyTargets,
    CutTargets,
    DeleteConfirmationState,
    DirectoryEntryState,
    LoadBrowserSnapshotEffect,
    LoadChildPaneSnapshotEffect,
    NameConflictState,
    NotificationState,
    PaneState,
    PasteClipboard,
    PasteConflictState,
    ResolvePasteConflict,
    RunClipboardPasteEffect,
    RunDirectorySizeEffect,
    SelectAllVisibleEntries,
    ToggleSelectionAndAdvance,
    build_initial_app_state,
    reduce_app_state,
)


def test_select_all_visible_entries_replaces_selection_with_visible_paths() -> None:
    initial_state = build_initial_app_state()
    state = replace(
        initial_state,
        current_pane=PaneState(
            directory_path="/home/tadashi/develop/zivo",
            entries=(
                DirectoryEntryState("/home/tadashi/develop/zivo/.env", ".env", "file", hidden=True),
                DirectoryEntryState("/home/tadashi/develop/zivo/docs", "docs", "dir"),
                DirectoryEntryState("/home/tadashi/develop/zivo/src", "src", "dir"),
            ),
            cursor_path="/home/tadashi/develop/zivo/docs",
            selected_paths=frozenset(
                {
                    "/home/tadashi/develop/zivo/.env",
                    "/home/tadashi/develop/zivo/docs",
                }
            ),
        ),
    )

    next_state = _reduce_state(
        state,
        SelectAllVisibleEntries(
            (
                "/home/tadashi/develop/zivo/docs",
                "/home/tadashi/develop/zivo/src",
            )
        ),
    )

    assert next_state.current_pane.selected_paths == frozenset(
        {
            "/home/tadashi/develop/zivo/docs",
            "/home/tadashi/develop/zivo/src",
        }
    )


def test_copy_targets_updates_clipboard_state() -> None:
    state = build_initial_app_state()

    next_state = _reduce_state(state, CopyTargets(("/home/tadashi/develop/zivo/docs",)))

    assert next_state.clipboard.mode == "copy"
    assert next_state.clipboard.paths == ("/home/tadashi/develop/zivo/docs",)


def test_copy_targets_warns_when_empty() -> None:
    state = build_initial_app_state()

    next_state = _reduce_state(state, CopyTargets(()))

    assert next_state.notification == NotificationState(level="warning", message="Nothing to copy")
    assert next_state.clipboard.mode == "none"


def test_cut_targets_warns_when_empty() -> None:
    state = build_initial_app_state()

    next_state = _reduce_state(state, CutTargets(()))

    assert next_state.notification == NotificationState(level="warning", message="Nothing to cut")
    assert next_state.clipboard.mode == "none"


def test_paste_clipboard_emits_paste_effect_and_sets_busy() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        CopyTargets(("/home/tadashi/develop/zivo/docs",)),
    )

    result = reduce_app_state(state, PasteClipboard())

    assert result.state.ui_mode == "BUSY"
    assert result.state.pending_paste_request_id == 1
    assert result.effects == (
        RunClipboardPasteEffect(
            request_id=1,
            request=result.effects[0].request,
        ),
    )
    assert result.effects[0].request.destination_dir == "/home/tadashi/develop/zivo"


def test_paste_clipboard_warns_when_empty() -> None:
    state = build_initial_app_state()

    next_state = _reduce_state(state, PasteClipboard())

    assert next_state.notification == NotificationState(
        level="warning",
        message="Clipboard is empty",
    )
    assert next_state.ui_mode == "BROWSING"


def test_paste_needs_resolution_enters_confirm_mode() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        CopyTargets(("/home/tadashi/develop/zivo/docs",)),
    )
    requested = reduce_app_state(state, PasteClipboard()).state

    conflict = PasteConflict(
        source_path="/home/tadashi/develop/zivo/docs",
        destination_path="/home/tadashi/develop/zivo/docs",
    )
    next_state = _reduce_state(
        requested,
        ClipboardPasteNeedsResolution(
            request_id=1,
            request=PasteRequest(
                mode="copy",
                source_paths=("/home/tadashi/develop/zivo/docs",),
                destination_dir="/home/tadashi/develop/zivo",
            ),
            conflicts=(conflict,),
        ),
    )

    assert next_state.ui_mode == "CONFIRM"
    assert isinstance(next_state.paste_conflict, PasteConflictState)
    assert next_state.paste_conflict.first_conflict == conflict


def test_paste_needs_resolution_uses_configured_default_resolution() -> None:
    state = _reduce_state(
        build_initial_app_state(paste_conflict_action="rename"),
        CopyTargets(("/home/tadashi/develop/zivo/docs",)),
    )
    requested = reduce_app_state(state, PasteClipboard()).state

    conflict = PasteConflict(
        source_path="/home/tadashi/develop/zivo/docs",
        destination_path="/home/tadashi/develop/zivo/docs",
    )
    result = reduce_app_state(
        requested,
        ClipboardPasteNeedsResolution(
            request_id=1,
            request=PasteRequest(
                mode="copy",
                source_paths=("/home/tadashi/develop/zivo/docs",),
                destination_dir="/home/tadashi/develop/zivo",
            ),
            conflicts=(conflict,),
        ),
    )

    assert result.state.ui_mode == "BUSY"
    assert result.effects == (
        RunClipboardPasteEffect(
            request_id=2,
            request=PasteRequest(
                mode="copy",
                source_paths=("/home/tadashi/develop/zivo/docs",),
                destination_dir="/home/tadashi/develop/zivo",
                conflict_resolution="rename",
            ),
        ),
    )


def test_paste_needs_resolution_ignores_stale_request() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        CopyTargets(("/home/tadashi/develop/zivo/docs",)),
    )
    requested = reduce_app_state(state, PasteClipboard()).state

    conflict = PasteConflict(
        source_path="/home/tadashi/develop/zivo/docs",
        destination_path="/home/tadashi/develop/zivo/docs",
    )
    next_state = _reduce_state(
        requested,
        ClipboardPasteNeedsResolution(
            request_id=99,
            request=PasteRequest(
                mode="copy",
                source_paths=("/home/tadashi/develop/zivo/docs",),
                destination_dir="/home/tadashi/develop/zivo",
            ),
            conflicts=(conflict,),
        ),
    )

    assert next_state == requested


def test_resolve_paste_conflict_restarts_paste_with_resolution() -> None:
    conflict = PasteConflict(
        source_path="/home/tadashi/develop/zivo/docs",
        destination_path="/home/tadashi/develop/zivo/docs",
    )
    state = replace(
        build_initial_app_state(),
        ui_mode="CONFIRM",
        paste_conflict=PasteConflictState(
            request=PasteRequest(
                mode="copy",
                source_paths=("/home/tadashi/develop/zivo/docs",),
                destination_dir="/home/tadashi/develop/zivo",
            ),
            conflicts=(conflict,),
            first_conflict=conflict,
        ),
        next_request_id=2,
        notification=None,
    )

    result = reduce_app_state(state, ResolvePasteConflict("rename"))

    assert result.state.ui_mode == "BUSY"
    assert result.effects == (
        RunClipboardPasteEffect(
            request_id=2,
            request=PasteRequest(
                mode="copy",
                source_paths=("/home/tadashi/develop/zivo/docs",),
                destination_dir="/home/tadashi/develop/zivo",
                conflict_resolution="rename",
            ),
        ),
    )


def test_clipboard_paste_completed_for_cut_clears_clipboard_and_requests_reload() -> None:
    state = _reduce_state(
        build_initial_app_state(),
        CutTargets(("/home/tadashi/develop/zivo/docs",)),
    )
    state = replace(state, pending_paste_request_id=4)

    result = reduce_app_state(
        state,
        ClipboardPasteCompleted(
            request_id=4,
            summary=PasteSummary(
                mode="cut",
                destination_dir="/home/tadashi/develop/zivo",
                total_count=1,
                success_count=1,
                skipped_count=0,
            ),
            applied_changes=(
                PasteAppliedChange(
                    source_path="/tmp/staging/docs",
                    destination_path="/home/tadashi/develop/zivo/docs",
                ),
            ),
        ),
    )

    assert result.state.clipboard.mode == "none"
    assert result.state.undo_stack == (
        UndoEntry(
            kind="paste_cut",
            steps=(
                UndoMovePathStep(
                    source_path="/home/tadashi/develop/zivo/docs",
                    destination_path="/tmp/staging/docs",
                ),
            ),
        ),
    )
    assert result.state.pending_browser_snapshot_request_id == 1
    assert result.effects == (
        LoadBrowserSnapshotEffect(
            request_id=1,
            path="/home/tadashi/develop/zivo",
            cursor_path="/home/tadashi/develop/zivo/docs",
            blocking=False,
            invalidate_paths=tuple(
                str(Path(p).resolve())
                for p in (
                    "/home/tadashi/develop/zivo",
                    "/home/tadashi/develop",
                    "/home/tadashi/develop/zivo/docs",
                )
            ),
        ),
    )


def test_clipboard_paste_completed_pushes_copy_undo_entry() -> None:
    state = replace(build_initial_app_state(), pending_paste_request_id=4)

    next_state = _reduce_state(
        state,
        ClipboardPasteCompleted(
            request_id=4,
            summary=PasteSummary(
                mode="copy",
                destination_dir="/home/tadashi/develop/zivo",
                total_count=1,
                success_count=1,
                skipped_count=0,
            ),
            applied_changes=(
                PasteAppliedChange(
                    source_path="/tmp/source/docs",
                    destination_path="/home/tadashi/develop/zivo/docs copy",
                ),
            ),
        ),
    )

    assert next_state.undo_stack == (
        UndoEntry(
            kind="paste_copy",
            steps=(UndoDeletePathStep(path="/home/tadashi/develop/zivo/docs copy"),),
        ),
    )


def test_clipboard_paste_completed_skips_undo_for_overwrite() -> None:
    state = replace(build_initial_app_state(), pending_paste_request_id=4)

    next_state = _reduce_state(
        state,
        ClipboardPasteCompleted(
            request_id=4,
            summary=PasteSummary(
                mode="copy",
                destination_dir="/home/tadashi/develop/zivo",
                total_count=1,
                success_count=1,
                skipped_count=0,
                overwrote_count=1,
            ),
            applied_changes=(
                PasteAppliedChange(
                    source_path="/tmp/source/docs",
                    destination_path="/home/tadashi/develop/zivo/docs",
                ),
            ),
        ),
    )

    assert next_state.undo_stack == ()
    assert next_state.post_reload_notification == NotificationState(
        level="info",
        message="Copied 1 item(s), undo unavailable for overwritten items",
    )


def test_clipboard_paste_failed_returns_to_browsing_and_clears_dialog_state() -> None:
    conflict = PasteConflict(
        source_path="/home/tadashi/develop/zivo/docs",
        destination_path="/home/tadashi/develop/zivo/docs",
    )
    state = replace(
        build_initial_app_state(),
        ui_mode="BUSY",
        pending_paste_request_id=4,
        paste_conflict=PasteConflictState(
            request=PasteRequest(
                mode="copy",
                source_paths=("/home/tadashi/develop/zivo/docs",),
                destination_dir="/home/tadashi/develop/zivo",
            ),
            conflicts=(conflict,),
            first_conflict=conflict,
        ),
        delete_confirmation=DeleteConfirmationState(paths=("/home/tadashi/develop/zivo/docs",)),
        name_conflict=NameConflictState(kind="rename", name="docs"),
    )

    next_state = _reduce_state(
        state,
        ClipboardPasteFailed(request_id=4, message="paste failed"),
    )

    assert next_state.ui_mode == "BROWSING"
    assert next_state.paste_conflict is None
    assert next_state.delete_confirmation is None
    assert next_state.name_conflict is None
    assert next_state.notification == NotificationState(level="error", message="paste failed")


def test_cancel_paste_conflict_returns_to_browsing_with_warning() -> None:
    state = replace(build_initial_app_state(), ui_mode="CONFIRM")

    next_state = _reduce_state(state, CancelPasteConflict())

    assert next_state.ui_mode == "BROWSING"
    assert next_state.notification == NotificationState(level="warning", message="Paste cancelled")


def test_toggle_selection_and_advance_moves_cursor_to_next_visible_entry() -> None:
    state = build_initial_app_state()
    current_path = "/home/tadashi/develop/zivo/docs"
    visible_paths = (
        "/home/tadashi/develop/zivo/docs",
        "/home/tadashi/develop/zivo/src",
        "/home/tadashi/develop/zivo/tests",
        "/home/tadashi/develop/zivo/README.md",
        "/home/tadashi/develop/zivo/pyproject.toml",
    )

    result = reduce_app_state(
        state,
        ToggleSelectionAndAdvance(path=current_path, visible_paths=visible_paths),
    )

    assert result.state.current_pane.selected_paths == frozenset({current_path})
    assert result.state.current_pane.cursor_path == "/home/tadashi/develop/zivo/src"
    assert result.state.pending_child_pane_request_id == 1
    assert result.effects == (
        LoadChildPaneSnapshotEffect(
            request_id=1,
            current_path="/home/tadashi/develop/zivo",
            cursor_path="/home/tadashi/develop/zivo/src",
        ),
        RunDirectorySizeEffect(
            request_id=2,
            paths=(
                "/home/tadashi/develop/zivo/docs",
                "/home/tadashi/develop/zivo/src",
                "/home/tadashi/develop/zivo/tests",
            ),
        ),
    )
