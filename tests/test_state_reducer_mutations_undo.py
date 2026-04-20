from dataclasses import replace
from pathlib import Path

from tests.test_state_reducer import _reduce_state
from zivo.models import (
    FileMutationResult,
    TrashRestoreRecord,
    UndoDeletePathStep,
    UndoEntry,
    UndoMovePathStep,
    UndoRestoreTrashStep,
    UndoResult,
)
from zivo.state import (
    LoadBrowserSnapshotEffect,
    NotificationState,
    PendingInputState,
    RunUndoEffect,
    build_initial_app_state,
    reduce_app_state,
)
from zivo.state.actions import (
    FileMutationCompleted,
    FileMutationFailed,
    UndoCompleted,
    UndoFailed,
    UndoLastOperation,
)


def test_undo_last_operation_warns_when_stack_is_empty() -> None:
    next_state = _reduce_state(build_initial_app_state(), UndoLastOperation())

    assert next_state.notification == NotificationState(level="warning", message="Nothing to undo")


def test_file_mutation_completed_requests_reload_with_result_cursor() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="BUSY",
        pending_file_mutation_request_id=4,
        pending_input=PendingInputState(
            prompt="New file: ",
            value="notes.txt",
            create_kind="file",
        ),
    )

    result = reduce_app_state(
        state,
        FileMutationCompleted(
            request_id=4,
            result=FileMutationResult(
                path="/home/tadashi/develop/zivo/notes.txt",
                message="Created file notes.txt",
            ),
        ),
    )

    assert result.state.ui_mode == "BROWSING"
    assert result.state.pending_input is None
    assert result.state.undo_stack == ()
    assert result.state.pending_browser_snapshot_request_id == 1
    assert result.effects == (
        LoadBrowserSnapshotEffect(
            request_id=1,
            path="/home/tadashi/develop/zivo",
            cursor_path="/home/tadashi/develop/zivo/notes.txt",
            blocking=False,
            invalidate_paths=tuple(
                str(Path(p).resolve())
                for p in (
                    "/home/tadashi/develop/zivo",
                    "/home/tadashi/develop",
                    "/home/tadashi/develop/zivo/notes.txt",
                )
            ),
        ),
    )

    rename_state = replace(
        build_initial_app_state(),
        ui_mode="BUSY",
        pending_file_mutation_request_id=4,
        pending_input=PendingInputState(
            prompt="Rename: ",
            value="manuals",
            target_path="/home/tadashi/develop/zivo/docs",
        ),
    )

    next_state = _reduce_state(
        rename_state,
        FileMutationCompleted(
            request_id=4,
            result=FileMutationResult(
                path="/home/tadashi/develop/zivo/manuals",
                message="Renamed to manuals",
                operation="rename",
                source_path="/home/tadashi/develop/zivo/docs",
            ),
        ),
    )

    assert next_state.undo_stack == (
        UndoEntry(
            kind="rename",
            steps=(
                UndoMovePathStep(
                    source_path="/home/tadashi/develop/zivo/manuals",
                    destination_path="/home/tadashi/develop/zivo/docs",
                ),
            ),
        ),
    )


def test_delete_file_mutation_completed_requests_reload_without_deleted_cursor() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="BUSY",
        pending_file_mutation_request_id=7,
        current_pane=replace(
            build_initial_app_state().current_pane,
            cursor_path="/home/tadashi/develop/zivo/docs",
        ),
    )

    result = reduce_app_state(
        state,
        FileMutationCompleted(
            request_id=7,
            result=FileMutationResult(
                path=None,
                message="Trashed 1 item",
                removed_paths=("/home/tadashi/develop/zivo/docs",),
            ),
        ),
    )

    assert result.state.ui_mode == "BROWSING"
    assert result.state.undo_stack == ()
    assert result.effects == (
        LoadBrowserSnapshotEffect(
            request_id=1,
            path="/home/tadashi/develop/zivo",
            cursor_path="/home/tadashi/develop/zivo/src",
            blocking=False,
            invalidate_paths=tuple(
                str(Path(p).resolve())
                for p in (
                    "/home/tadashi/develop/zivo",
                    "/home/tadashi/develop",
                    "/home/tadashi/develop/zivo/src",
                )
            ),
        ),
    )

    undo_state = replace(
        build_initial_app_state(),
        ui_mode="BUSY",
        pending_file_mutation_request_id=7,
    )

    next_state = _reduce_state(
        undo_state,
        FileMutationCompleted(
            request_id=7,
            result=FileMutationResult(
                path=None,
                message="Trashed 1 item",
                removed_paths=("/home/tadashi/develop/zivo/docs",),
                operation="delete",
                delete_mode="trash",
                trash_records=(
                    TrashRestoreRecord(
                        original_path="/home/tadashi/develop/zivo/docs",
                        trashed_path="/home/tadashi/.local/share/Trash/files/docs",
                        metadata_path="/home/tadashi/.local/share/Trash/info/docs.trashinfo",
                    ),
                ),
            ),
        ),
    )

    assert next_state.undo_stack == (
        UndoEntry(
            kind="trash_delete",
            steps=(
                UndoRestoreTrashStep(
                    record=TrashRestoreRecord(
                        original_path="/home/tadashi/develop/zivo/docs",
                        trashed_path="/home/tadashi/.local/share/Trash/files/docs",
                        metadata_path="/home/tadashi/.local/share/Trash/info/docs.trashinfo",
                    )
                ),
            ),
        ),
    )


def test_undo_last_operation_runs_effect() -> None:
    entry = UndoEntry(kind="paste_copy", steps=(UndoDeletePathStep(path="/tmp/copied"),))
    state = replace(build_initial_app_state(), undo_stack=(entry,), next_request_id=6)

    result = reduce_app_state(state, UndoLastOperation())

    assert result.state.pending_undo_entry == entry
    assert result.state.pending_undo_request_id == 6
    assert result.state.ui_mode == "BUSY"
    assert result.effects == (RunUndoEffect(request_id=6, entry=entry),)


def test_undo_completed_pops_stack_and_requests_reload() -> None:
    entry = UndoEntry(kind="paste_copy", steps=(UndoDeletePathStep(path="/tmp/copied"),))
    state = replace(
        build_initial_app_state(),
        undo_stack=(entry,),
        pending_undo_entry=entry,
        pending_undo_request_id=9,
        next_request_id=4,
    )

    result = reduce_app_state(
        state,
        UndoCompleted(
            request_id=9,
            entry=entry,
            result=UndoResult(
                path=None,
                message="Undid copied item",
                removed_paths=("/tmp/copied",),
            ),
        ),
    )

    assert result.state.undo_stack == ()
    assert result.state.pending_undo_request_id is None
    assert result.state.post_reload_notification == NotificationState(
        level="info",
        message="Undid copied item",
    )
    assert result.effects == (
        LoadBrowserSnapshotEffect(
            request_id=4,
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


def test_undo_failed_returns_error_without_popping_stack() -> None:
    entry = UndoEntry(kind="paste_copy", steps=(UndoDeletePathStep(path="/tmp/copied"),))
    state = replace(
        build_initial_app_state(),
        undo_stack=(entry,),
        pending_undo_entry=entry,
        pending_undo_request_id=9,
        ui_mode="BUSY",
    )

    next_state = _reduce_state(state, UndoFailed(request_id=9, message="permission denied"))

    assert next_state.pending_undo_request_id is None
    assert next_state.undo_stack == (entry,)
    assert next_state.notification == NotificationState(
        level="error",
        message="permission denied",
    )


def test_file_mutation_failed_keeps_input_value_and_returns_error() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="BUSY",
        pending_file_mutation_request_id=3,
        pending_input=PendingInputState(
            prompt="Rename: ",
            value="docs copy",
            target_path="/home/tadashi/develop/zivo/docs",
        ),
    )

    next_state = _reduce_state(state, FileMutationFailed(request_id=3, message="permission denied"))

    assert next_state.ui_mode == "RENAME"
    assert next_state.pending_input is not None
    assert next_state.pending_input.value == "docs copy"
    assert next_state.notification == NotificationState(
        level="error",
        message="permission denied",
    )


def test_delete_file_mutation_failed_returns_to_browsing() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="BUSY",
        pending_file_mutation_request_id=5,
    )

    next_state = _reduce_state(state, FileMutationFailed(request_id=5, message="trash failed"))

    assert next_state.ui_mode == "BROWSING"
    assert next_state.notification == NotificationState(
        level="error",
        message="trash failed",
    )
