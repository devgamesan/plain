from dataclasses import replace
from pathlib import Path

from tests.test_state_reducer import _reduce_state
from zivo.models import (
    CreateZipArchiveRequest,
    CreateZipArchiveResult,
    ExtractArchiveRequest,
    ExtractArchiveResult,
)
from zivo.state import (
    ArchiveExtractCompleted,
    ArchiveExtractConfirmationState,
    ArchiveExtractFailed,
    ArchiveExtractProgress,
    ArchiveExtractProgressState,
    ArchivePreparationCompleted,
    ArchivePreparationFailed,
    CancelArchiveExtractConfirmation,
    CancelZipCompressConfirmation,
    ConfirmArchiveExtract,
    ConfirmZipCompress,
    LoadBrowserSnapshotEffect,
    NotificationState,
    PendingInputState,
    RunArchiveExtractEffect,
    RunArchivePreparationEffect,
    RunZipCompressEffect,
    RunZipCompressPreparationEffect,
    ZipCompressCompleted,
    ZipCompressConfirmationState,
    ZipCompressFailed,
    ZipCompressPreparationCompleted,
    ZipCompressProgress,
    ZipCompressProgressState,
    build_initial_app_state,
    reduce_app_state,
)
from zivo.state.reducer_common import browser_snapshot_invalidation_paths


def test_submit_pending_extract_starts_archive_preparation() -> None:
    from zivo.state import SubmitPendingInput

    source_path = "/home/tadashi/develop/zivo/archive.zip"
    dest_path = "/tmp/output/archive"
    state = replace(
        build_initial_app_state(),
        ui_mode="EXTRACT",
        pending_input=PendingInputState(
            prompt="Extract to: ",
            value=dest_path,
            extract_source_path=source_path,
        ),
    )

    result = reduce_app_state(state, SubmitPendingInput())

    assert result.state.pending_archive_prepare_request_id == 1
    assert result.state.ui_mode == "BUSY"
    assert result.effects == (
        RunArchivePreparationEffect(
            request_id=1,
            request=ExtractArchiveRequest(
                source_path=str(Path(source_path).resolve()),
                destination_path=str(Path(dest_path).resolve()),
            ),
        ),
    )


def test_submit_pending_zip_compress_starts_preparation() -> None:
    from zivo.state import SubmitPendingInput

    dest_path = "/tmp/output.zip"
    state = replace(
        build_initial_app_state(),
        ui_mode="ZIP",
        pending_input=PendingInputState(
            prompt="Compress to: ",
            value=dest_path,
            zip_source_paths=(
                "/home/tadashi/develop/zivo/docs",
                "/home/tadashi/develop/zivo/src",
            ),
        ),
    )

    result = reduce_app_state(state, SubmitPendingInput())

    assert result.state.pending_zip_compress_prepare_request_id == 1
    assert result.state.ui_mode == "BUSY"
    assert result.effects == (
        RunZipCompressPreparationEffect(
            request_id=1,
            request=CreateZipArchiveRequest(
                source_paths=(
                    "/home/tadashi/develop/zivo/docs",
                    "/home/tadashi/develop/zivo/src",
                ),
                destination_path=str(Path(dest_path).resolve()),
                root_dir="/home/tadashi/develop/zivo",
            ),
        ),
    )


def test_submit_pending_extract_resolves_relative_destination_from_archive_parent() -> None:
    from zivo.state import SubmitPendingInput

    source_path = "/home/tadashi/develop/zivo/docs/archive.tar.bz2"
    state = replace(
        build_initial_app_state(),
        ui_mode="EXTRACT",
        pending_input=PendingInputState(
            prompt="Extract to: ",
            value="../exports/archive",
            extract_source_path=source_path,
        ),
    )

    result = reduce_app_state(state, SubmitPendingInput())

    assert result.effects == (
        RunArchivePreparationEffect(
            request_id=1,
            request=ExtractArchiveRequest(
                source_path=str(Path(source_path).resolve()),
                destination_path=str(Path("/home/tadashi/develop/zivo/exports/archive").resolve()),
            ),
        ),
    )


def test_archive_preparation_with_conflicts_enters_confirm_mode() -> None:
    request = ExtractArchiveRequest(
        source_path="/home/tadashi/develop/zivo/archive.zip",
        destination_path="/tmp/output/archive",
    )
    state = replace(
        build_initial_app_state(),
        ui_mode="BUSY",
        pending_input=PendingInputState(
            prompt="Extract to: ",
            value="/tmp/output/archive",
            extract_source_path=request.source_path,
        ),
        pending_archive_prepare_request_id=4,
    )

    next_state = _reduce_state(
        state,
        ArchivePreparationCompleted(
            request_id=4,
            request=request,
            total_entries=7,
            conflict_count=2,
            first_conflict_path="/tmp/output/archive/notes.txt",
        ),
    )

    assert next_state.ui_mode == "CONFIRM"
    assert next_state.pending_archive_prepare_request_id is None
    assert next_state.archive_extract_confirmation == ArchiveExtractConfirmationState(
        request=request,
        conflict_count=2,
        first_conflict_path="/tmp/output/archive/notes.txt",
        total_entries=7,
    )


def test_zip_compress_preparation_with_existing_destination_enters_confirm_mode() -> None:
    request = CreateZipArchiveRequest(
        source_paths=("/home/tadashi/develop/zivo/docs",),
        destination_path="/home/tadashi/develop/zivo/docs.zip",
        root_dir="/home/tadashi/develop/zivo",
    )
    state = replace(
        build_initial_app_state(),
        ui_mode="BUSY",
        pending_input=PendingInputState(
            prompt="Compress to: ",
            value="/home/tadashi/develop/zivo/docs.zip",
            zip_source_paths=request.source_paths,
        ),
        pending_zip_compress_prepare_request_id=4,
    )

    next_state = _reduce_state(
        state,
        ZipCompressPreparationCompleted(
            request_id=4,
            request=request,
            total_entries=7,
            destination_exists=True,
        ),
    )

    assert next_state.ui_mode == "CONFIRM"
    assert next_state.pending_zip_compress_prepare_request_id is None
    assert next_state.zip_compress_confirmation == ZipCompressConfirmationState(
        request=request,
        total_entries=7,
    )


def test_confirm_archive_extract_runs_extract_effect() -> None:
    request = ExtractArchiveRequest(
        source_path="/home/tadashi/develop/zivo/archive.zip",
        destination_path="/tmp/output/archive",
    )
    state = replace(
        build_initial_app_state(),
        ui_mode="CONFIRM",
        pending_input=PendingInputState(
            prompt="Extract to: ",
            value="/tmp/output/archive",
            extract_source_path=request.source_path,
        ),
        archive_extract_confirmation=ArchiveExtractConfirmationState(
            request=request,
            conflict_count=1,
            first_conflict_path="/tmp/output/archive/notes.txt",
            total_entries=3,
        ),
    )

    result = reduce_app_state(state, ConfirmArchiveExtract())

    assert result.state.pending_archive_extract_request_id == 1
    assert result.effects == (RunArchiveExtractEffect(request_id=1, request=request),)


def test_confirm_zip_compress_runs_effect() -> None:
    request = CreateZipArchiveRequest(
        source_paths=("/home/tadashi/develop/zivo/docs",),
        destination_path="/home/tadashi/develop/zivo/docs.zip",
        root_dir="/home/tadashi/develop/zivo",
    )
    state = replace(
        build_initial_app_state(),
        ui_mode="CONFIRM",
        pending_input=PendingInputState(
            prompt="Compress to: ",
            value="/home/tadashi/develop/zivo/docs.zip",
            zip_source_paths=request.source_paths,
        ),
        zip_compress_confirmation=ZipCompressConfirmationState(
            request=request,
            total_entries=3,
        ),
    )

    result = reduce_app_state(state, ConfirmZipCompress())

    assert result.state.pending_zip_compress_request_id == 1
    assert result.effects == (RunZipCompressEffect(request_id=1, request=request),)


def test_cancel_archive_extract_confirmation_returns_to_extract_mode() -> None:
    request = ExtractArchiveRequest(
        source_path="/home/tadashi/develop/zivo/archive.zip",
        destination_path="/tmp/output/archive",
    )
    state = replace(
        build_initial_app_state(),
        ui_mode="CONFIRM",
        pending_input=PendingInputState(
            prompt="Extract to: ",
            value="/tmp/output/archive",
            extract_source_path=request.source_path,
        ),
        archive_extract_confirmation=ArchiveExtractConfirmationState(
            request=request,
            conflict_count=1,
            first_conflict_path="/tmp/output/archive/notes.txt",
            total_entries=3,
        ),
    )

    next_state = _reduce_state(state, CancelArchiveExtractConfirmation())

    assert next_state.ui_mode == "EXTRACT"
    assert next_state.archive_extract_confirmation is None
    assert next_state.notification == NotificationState(
        level="warning",
        message="Extraction cancelled",
    )


def test_cancel_zip_compress_confirmation_returns_to_zip_mode() -> None:
    request = CreateZipArchiveRequest(
        source_paths=("/home/tadashi/develop/zivo/docs",),
        destination_path="/home/tadashi/develop/zivo/docs.zip",
        root_dir="/home/tadashi/develop/zivo",
    )
    state = replace(
        build_initial_app_state(),
        ui_mode="CONFIRM",
        pending_input=PendingInputState(
            prompt="Compress to: ",
            value="/home/tadashi/develop/zivo/docs.zip",
            zip_source_paths=request.source_paths,
        ),
        zip_compress_confirmation=ZipCompressConfirmationState(
            request=request,
            total_entries=3,
        ),
    )

    next_state = _reduce_state(state, CancelZipCompressConfirmation())

    assert next_state.ui_mode == "ZIP"
    assert next_state.zip_compress_confirmation is None
    assert next_state.notification == NotificationState(
        level="warning",
        message="Zip compression cancelled",
    )


def test_archive_extract_progress_updates_notification() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="BUSY",
        pending_archive_extract_request_id=6,
    )

    next_state = _reduce_state(
        state,
        ArchiveExtractProgress(
            request_id=6,
            completed_entries=2,
            total_entries=5,
            current_path="/tmp/output/archive/notes.txt",
        ),
    )

    assert next_state.archive_extract_progress == ArchiveExtractProgressState(
        completed_entries=2,
        total_entries=5,
        current_path="/tmp/output/archive/notes.txt",
    )
    assert next_state.notification == NotificationState(
        level="info",
        message="Extracting archive 2/5: notes.txt",
    )


def test_zip_compress_progress_updates_notification() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="BUSY",
        pending_zip_compress_request_id=6,
    )

    next_state = _reduce_state(
        state,
        ZipCompressProgress(
            request_id=6,
            completed_entries=2,
            total_entries=5,
            current_path="/home/tadashi/develop/zivo/docs/readme.txt",
        ),
    )

    assert next_state.zip_compress_progress == ZipCompressProgressState(
        completed_entries=2,
        total_entries=5,
        current_path="/home/tadashi/develop/zivo/docs/readme.txt",
    )
    assert next_state.notification == NotificationState(
        level="info",
        message="Compressing as zip 2/5: readme.txt",
    )


def test_archive_extract_completed_requests_snapshot_for_destination_parent() -> None:
    dest_parent = str(Path("/tmp/output").resolve())
    dest_path = str(Path("/tmp/output/archive").resolve())
    state = replace(
        build_initial_app_state(),
        ui_mode="BUSY",
        pending_input=PendingInputState(
            prompt="Extract to: ",
            value=dest_path,
            extract_source_path="/home/tadashi/develop/zivo/archive.zip",
        ),
        pending_archive_extract_request_id=9,
    )

    result = reduce_app_state(
        state,
        ArchiveExtractCompleted(
            request_id=9,
            result=ExtractArchiveResult(
                destination_path=dest_path,
                extracted_entries=2,
                total_entries=2,
                message="Extracted 2 entries to archive",
            ),
        ),
    )

    assert result.state.post_reload_notification == NotificationState(
        level="info",
        message="Extracted 2 entries to archive",
    )
    assert result.effects == (
        LoadBrowserSnapshotEffect(
            request_id=1,
            path=dest_parent,
            cursor_path=dest_path,
            blocking=True,
            invalidate_paths=browser_snapshot_invalidation_paths(dest_parent, dest_path),
        ),
    )


def test_zip_compress_completed_requests_snapshot_for_destination_parent() -> None:
    dest_parent = str(Path("/tmp").resolve())
    dest_path = str(Path("/tmp/output.zip").resolve())
    state = replace(
        build_initial_app_state(),
        ui_mode="BUSY",
        pending_input=PendingInputState(
            prompt="Compress to: ",
            value=dest_path,
            zip_source_paths=("/home/tadashi/develop/zivo/docs",),
        ),
        pending_zip_compress_request_id=9,
    )

    result = reduce_app_state(
        state,
        ZipCompressCompleted(
            request_id=9,
            result=CreateZipArchiveResult(
                destination_path=dest_path,
                archived_entries=2,
                total_entries=2,
                message="Created output.zip with 2 entries",
            ),
        ),
    )

    assert result.state.post_reload_notification == NotificationState(
        level="info",
        message="Created output.zip with 2 entries",
    )
    assert result.effects == (
        LoadBrowserSnapshotEffect(
            request_id=1,
            path=dest_parent,
            cursor_path=dest_path,
            blocking=True,
            invalidate_paths=browser_snapshot_invalidation_paths(dest_parent, dest_path),
        ),
    )


def test_archive_extract_failed_returns_to_extract_mode() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="BUSY",
        pending_input=PendingInputState(
            prompt="Extract to: ",
            value="/tmp/output/archive",
            extract_source_path="/home/tadashi/develop/zivo/archive.zip",
        ),
        pending_archive_extract_request_id=12,
    )

    next_state = _reduce_state(
        state,
        ArchiveExtractFailed(request_id=12, message="Unsupported archive member type: link"),
    )

    assert next_state.ui_mode == "EXTRACT"
    assert next_state.pending_archive_extract_request_id is None
    assert next_state.notification == NotificationState(
        level="error",
        message="Unsupported archive member type: link",
    )


def test_zip_compress_failed_returns_to_zip_mode() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="BUSY",
        pending_input=PendingInputState(
            prompt="Compress to: ",
            value="/tmp/output.zip",
            zip_source_paths=("/home/tadashi/develop/zivo/docs",),
        ),
        pending_zip_compress_request_id=12,
    )

    next_state = _reduce_state(
        state,
        ZipCompressFailed(request_id=12, message="Destination path already exists as a directory"),
    )

    assert next_state.ui_mode == "ZIP"
    assert next_state.pending_zip_compress_request_id is None
    assert next_state.notification == NotificationState(
        level="error",
        message="Destination path already exists as a directory",
    )


def test_archive_preparation_failed_returns_to_extract_mode() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="BUSY",
        pending_input=PendingInputState(
            prompt="Extract to: ",
            value="/tmp/output/archive",
            extract_source_path="/home/tadashi/develop/zivo/archive.zip",
        ),
        pending_archive_prepare_request_id=7,
    )

    next_state = _reduce_state(
        state,
        ArchivePreparationFailed(request_id=7, message="Unsupported archive format: archive.rar"),
    )

    assert next_state.ui_mode == "EXTRACT"
    assert next_state.pending_archive_prepare_request_id is None
    assert next_state.notification == NotificationState(
        level="error",
        message="Unsupported archive format: archive.rar",
    )
