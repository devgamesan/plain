from dataclasses import replace
from pathlib import Path

from tests.test_state_reducer import _reduce_state
from zivo.models import CreatePathRequest, RenameRequest
from zivo.state import (
    BeginCreateInput,
    BeginExtractArchiveInput,
    BeginRenameInput,
    BeginZipCompressInput,
    DismissNameConflict,
    NameConflictState,
    NotificationState,
    PendingInputState,
    RunFileMutationEffect,
    SetPendingInputValue,
    SubmitPendingInput,
    build_initial_app_state,
    reduce_app_state,
)


def test_begin_rename_input_sets_initial_value_from_target_name() -> None:
    state = build_initial_app_state()

    next_state = _reduce_state(state, BeginRenameInput("/home/tadashi/develop/zivo/docs"))

    assert next_state.ui_mode == "RENAME"
    assert next_state.pending_input == PendingInputState(
        prompt="Rename: ",
        value="docs",
        cursor_pos=4,
        target_path="/home/tadashi/develop/zivo/docs",
    )


def test_begin_rename_input_ignores_unknown_path() -> None:
    state = build_initial_app_state()

    next_state = _reduce_state(state, BeginRenameInput("/tmp/missing"))

    assert next_state == state


def test_begin_create_input_sets_mode_and_kind() -> None:
    state = build_initial_app_state()

    next_state = _reduce_state(state, BeginCreateInput("dir"))

    assert next_state.ui_mode == "CREATE"
    assert next_state.pending_input == PendingInputState(
        prompt="New directory: ",
        value="",
        create_kind="dir",
    )


def test_begin_extract_archive_input_sets_default_destination() -> None:
    archive_path = "/home/tadashi/develop/zivo/archive.tar.gz"
    expected_value = str(Path("/home/tadashi/develop/zivo/archive").resolve())
    next_state = _reduce_state(
        build_initial_app_state(),
        BeginExtractArchiveInput(archive_path),
    )

    assert next_state.ui_mode == "EXTRACT"
    assert next_state.pending_input == PendingInputState(
        prompt="Extract to: ",
        value=expected_value,
        cursor_pos=len(expected_value),
        extract_source_path=archive_path,
    )


def test_begin_zip_compress_input_sets_default_destination() -> None:
    source_path = "/home/tadashi/develop/zivo/README.md"
    expected_value = str(Path("/home/tadashi/develop/zivo/README.zip").resolve())
    next_state = _reduce_state(
        build_initial_app_state(),
        BeginZipCompressInput((source_path,)),
    )

    assert next_state.ui_mode == "ZIP"
    assert next_state.pending_input == PendingInputState(
        prompt="Compress to: ",
        value=expected_value,
        cursor_pos=len(expected_value),
        zip_source_paths=(source_path,),
    )


def test_cancel_pending_input_returns_to_browsing() -> None:
    from zivo.state import CancelPendingInput

    state = replace(
        build_initial_app_state(),
        ui_mode="RENAME",
        pending_input=PendingInputState(prompt="Rename: ", value="docs"),
    )

    next_state = _reduce_state(state, CancelPendingInput())

    assert next_state.ui_mode == "BROWSING"
    assert next_state.pending_input is None


def test_set_pending_input_value_updates_current_value() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="CREATE",
        pending_input=PendingInputState(prompt="New file: ", value="", create_kind="file"),
    )

    next_state = _reduce_state(state, SetPendingInputValue("notes.txt", cursor_pos=8))

    assert next_state.pending_input is not None
    assert next_state.pending_input.value == "notes.txt"


def test_submit_pending_input_rejects_duplicate_name() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="CREATE",
        pending_input=PendingInputState(
            prompt="New file: ",
            value="README.md",
            create_kind="file",
        ),
    )

    next_state = _reduce_state(state, SubmitPendingInput())

    assert next_state.ui_mode == "CONFIRM"
    assert next_state.pending_input is not None
    assert next_state.notification is None
    assert next_state.name_conflict == NameConflictState(
        kind="create_file",
        name="README.md",
    )


def test_submit_pending_input_treats_unchanged_rename_as_noop() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="RENAME",
        pending_input=PendingInputState(
            prompt="Rename: ",
            value="docs",
            target_path="/home/tadashi/develop/zivo/docs",
        ),
    )

    next_state = _reduce_state(state, SubmitPendingInput())

    assert next_state.ui_mode == "BROWSING"
    assert next_state.pending_input is None
    assert next_state.notification == NotificationState(level="info", message="Name unchanged")


def test_submit_pending_input_emits_file_mutation_effect() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="RENAME",
        pending_input=PendingInputState(
            prompt="Rename: ",
            value="manuals",
            target_path="/home/tadashi/develop/zivo/docs",
        ),
    )

    result = reduce_app_state(state, SubmitPendingInput())

    assert result.state.ui_mode == "BUSY"
    assert result.state.pending_file_mutation_request_id == 1
    assert result.effects == (
        RunFileMutationEffect(
            request_id=1,
            request=RenameRequest(
                source_path="/home/tadashi/develop/zivo/docs",
                new_name="manuals",
            ),
        ),
    )


def test_submit_pending_input_emits_create_effect() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="CREATE",
        pending_input=PendingInputState(
            prompt="New file: ",
            value="notes.txt",
            create_kind="file",
        ),
    )

    result = reduce_app_state(state, SubmitPendingInput())

    assert result.effects == (
        RunFileMutationEffect(
            request_id=1,
            request=CreatePathRequest(
                parent_dir="/home/tadashi/develop/zivo",
                name="notes.txt",
                kind="file",
            ),
        ),
    )


def test_submit_pending_input_name_conflict_enters_confirm_mode_for_rename() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="RENAME",
        pending_input=PendingInputState(
            prompt="Rename: ",
            value="src",
            target_path="/home/tadashi/develop/zivo/docs",
        ),
    )

    result = reduce_app_state(state, SubmitPendingInput())

    assert result.state.ui_mode == "CONFIRM"
    assert result.state.notification is None
    assert result.state.name_conflict == NameConflictState(kind="rename", name="src")
    assert result.effects == ()


def test_submit_pending_input_name_conflict_enters_confirm_mode_for_create_dir() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="CREATE",
        pending_input=PendingInputState(
            prompt="New directory: ",
            value="docs",
            create_kind="dir",
        ),
    )

    result = reduce_app_state(state, SubmitPendingInput())

    assert result.state.ui_mode == "CONFIRM"
    assert result.state.name_conflict == NameConflictState(kind="create_dir", name="docs")
    assert result.effects == ()


def test_dismiss_name_conflict_restores_rename_mode_and_keeps_input() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="CONFIRM",
        pending_input=PendingInputState(
            prompt="Rename: ",
            value="src",
            target_path="/home/tadashi/develop/zivo/docs",
        ),
        name_conflict=NameConflictState(kind="rename", name="src"),
    )

    next_state = _reduce_state(state, DismissNameConflict())

    assert next_state.ui_mode == "RENAME"
    assert next_state.pending_input == state.pending_input
    assert next_state.name_conflict is None


def test_dismiss_name_conflict_restores_create_mode_and_keeps_input() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="CONFIRM",
        pending_input=PendingInputState(
            prompt="New file: ",
            value="docs",
            create_kind="file",
        ),
        name_conflict=NameConflictState(kind="create_file", name="docs"),
    )

    next_state = _reduce_state(state, DismissNameConflict())

    assert next_state.ui_mode == "CREATE"
    assert next_state.pending_input == state.pending_input
    assert next_state.name_conflict is None


def test_submit_pending_input_case_only_rename_emits_mutation() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="RENAME",
        pending_input=PendingInputState(
            prompt="Rename: ",
            value="Docs",
            target_path="/home/tadashi/develop/zivo/docs",
        ),
    )

    result = reduce_app_state(state, SubmitPendingInput())

    assert result.state.ui_mode == "BUSY"
    assert result.effects == (
        RunFileMutationEffect(
            request_id=1,
            request=RenameRequest(
                source_path="/home/tadashi/develop/zivo/docs",
                new_name="Docs",
            ),
        ),
    )


def test_submit_pending_input_case_insensitive_conflict_on_macos(monkeypatch) -> None:
    import zivo.state.reducer_common as rc

    monkeypatch.setattr(rc, "_is_macos", True)
    state = replace(
        build_initial_app_state(),
        ui_mode="RENAME",
        pending_input=PendingInputState(
            prompt="Rename: ",
            value="Src",
            target_path="/home/tadashi/develop/zivo/docs",
        ),
    )

    result = reduce_app_state(state, SubmitPendingInput())

    assert result.state.ui_mode == "CONFIRM"
    assert result.state.name_conflict == NameConflictState(kind="rename", name="Src")


def test_submit_pending_input_case_sensitive_no_conflict_on_linux(monkeypatch) -> None:
    import zivo.state.reducer_common as rc

    monkeypatch.setattr(rc, "_is_macos", False)
    state = replace(
        build_initial_app_state(),
        ui_mode="RENAME",
        pending_input=PendingInputState(
            prompt="Rename: ",
            value="Src",
            target_path="/home/tadashi/develop/zivo/docs",
        ),
    )

    result = reduce_app_state(state, SubmitPendingInput())

    assert result.state.ui_mode == "BUSY"
    assert result.effects != ()


def test_submit_pending_input_rejects_colon_in_name_on_macos(monkeypatch) -> None:
    import zivo.state.reducer_common as rc

    monkeypatch.setattr(rc, "_is_macos", True)
    state = replace(
        build_initial_app_state(),
        ui_mode="CREATE",
        pending_input=PendingInputState(
            prompt="New file: ",
            value="file:name.txt",
            create_kind="file",
        ),
    )

    next_state = _reduce_state(state, SubmitPendingInput())

    assert next_state.notification is not None
    assert next_state.notification.level == "error"
    assert "colons" in next_state.notification.message


def test_submit_pending_input_allows_colon_in_name_on_linux(monkeypatch) -> None:
    import zivo.state.reducer_common as rc

    monkeypatch.setattr(rc, "_is_macos", False)
    state = replace(
        build_initial_app_state(),
        ui_mode="CREATE",
        pending_input=PendingInputState(
            prompt="New file: ",
            value="file:name.txt",
            create_kind="file",
        ),
    )

    result = reduce_app_state(state, SubmitPendingInput())

    assert result.state.ui_mode == "BUSY"
    assert result.effects != ()
