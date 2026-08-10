from dataclasses import replace

from zivo.models import (
    CreateZipArchiveRequest,
    DuplicateFailure,
    DuplicateRequest,
    DuplicateSummary,
    ExtractArchiveRequest,
    PasteConflict,
    PasteFailure,
    PasteRequest,
    PasteSummary,
    UndoDeletePathStep,
    UndoEntry,
)
from zivo.state import (
    NotificationAction,
    NotificationDetails,
    NotificationFailureDetail,
    NotificationState,
    build_initial_app_state,
    reduce_app_state,
    select_notification_details_dialog_state,
)
from zivo.state.actions import (
    ActivateNotificationAction,
    ArchivePreparationFailed,
    BeginCommandPalette,
    ClipboardPasteNeedsResolution,
    DismissNotification,
    SetNotification,
    SubmitCommandPalette,
    ZipCompressPreparationFailed,
)
from zivo.state.command_palette import get_command_palette_items
from zivo.state.effects import (
    RunArchivePreparationEffect,
    RunClipboardPasteEffect,
    RunDuplicateEffect,
    RunZipCompressPreparationEffect,
)
from zivo.state.reducer_requests import (
    notification_for_duplicate_summary,
    notification_for_paste_summary,
)


def test_paste_success_prefers_undo_and_auto_dismisses() -> None:
    entry = UndoEntry(
        kind="paste_copy",
        steps=(UndoDeletePathStep(path="/tmp/copied.txt"),),
    )
    notification = notification_for_paste_summary(
        PasteSummary(
            mode="copy",
            destination_dir="/tmp",
            total_count=1,
            success_count=1,
            skipped_count=0,
        ),
        undo_entry=entry,
    )

    assert notification.action == NotificationAction(
        action_id="notification.undo",
        label="Undo",
        payload=entry,
    )
    assert notification.auto_dismiss is True


def test_partial_paste_prefers_details_without_auto_dismiss() -> None:
    notification = notification_for_paste_summary(
        PasteSummary(
            mode="copy",
            destination_dir="/tmp",
            total_count=2,
            success_count=1,
            skipped_count=0,
            failures=(
                PasteFailure(
                    source_path="/tmp/source.txt",
                    destination_path="/tmp/destination/source.txt",
                    message="permission denied",
                ),
            ),
        )
    )
    assert notification.action is not None
    assert notification.action.action_id == "notification.details"
    assert notification.auto_dismiss is False


def test_paste_failure_details_and_retry_allowlist() -> None:
    request = PasteRequest(
        mode="copy",
        source_paths=("/tmp/source.txt",),
        destination_dir="/tmp/destination",
    )
    failure_summary = PasteSummary(
        mode="copy",
        destination_dir="/tmp/destination",
        total_count=1,
        success_count=0,
        skipped_count=0,
        failures=(
            PasteFailure(
                source_path="/tmp/source.txt",
                destination_path="/tmp/destination/source.txt",
                message="permission denied",
            ),
        ),
    )
    retry_notification = notification_for_paste_summary(
        failure_summary,
        request=request,
    )
    assert retry_notification.action is not None
    assert retry_notification.action.action_id == "notification.retry"
    assert retry_notification.auto_dismiss is False

    skipped_notification = notification_for_paste_summary(
        replace(failure_summary, skipped_count=1),
        request=request,
    )
    assert skipped_notification.action is not None
    assert skipped_notification.action.action_id == "notification.details"

    conflict_notification = notification_for_paste_summary(
        failure_summary,
        request=replace(request, conflict_resolution="rename"),
    )
    assert conflict_notification.action is not None
    assert conflict_notification.action.action_id == "notification.details"
    assert conflict_notification.details is not None

    overwritten_notification = notification_for_paste_summary(
        replace(failure_summary, overwrote_count=1),
        request=request,
    )
    assert overwritten_notification.action is not None
    assert overwritten_notification.action.action_id == "notification.details"
    assert overwritten_notification.details is not None


def test_duplicate_failure_with_applied_change_cannot_retry() -> None:
    request = DuplicateRequest(
        source_paths=("/tmp/source.txt",),
        destination_dir="/tmp",
    )
    summary = DuplicateSummary(
        destination_dir="/tmp",
        total_count=1,
        success_count=0,
        failures=(
            DuplicateFailure(
                source_path="/tmp/source.txt",
                destination_path="/tmp/source copy.txt",
                message="permission denied",
            ),
        ),
    )
    notification = notification_for_duplicate_summary(
        summary,
        request=request,
        applied_changes_count=1,
    )
    assert notification.action is not None
    assert notification.action.action_id == "notification.details"
    assert notification.details is not None
    assert notification.auto_dismiss is False


def test_duplicate_retry_allowlist_requires_no_success_or_applied_change() -> None:
    request = DuplicateRequest(
        source_paths=("/tmp/source.txt",),
        destination_dir="/tmp",
    )
    failure = DuplicateFailure(
        source_path="/tmp/source.txt",
        destination_path="/tmp/source copy.txt",
        message="permission denied",
    )
    retry = notification_for_duplicate_summary(
        DuplicateSummary(
            destination_dir="/tmp",
            total_count=1,
            success_count=0,
            failures=(failure,),
        ),
        request=request,
        applied_changes_count=0,
    )
    partial = notification_for_duplicate_summary(
        DuplicateSummary(
            destination_dir="/tmp",
            total_count=2,
            success_count=1,
            failures=(failure,),
        ),
        request=request,
        applied_changes_count=1,
    )

    assert retry.action is not None
    assert retry.action.action_id == "notification.retry"
    assert retry.auto_dismiss is False
    assert partial.action is not None
    assert partial.action.action_id == "notification.details"
    assert partial.auto_dismiss is False


def test_archive_and_zip_preparation_failures_expose_retry_only() -> None:
    archive_request = ExtractArchiveRequest("/tmp/archive.zip", "/tmp/archive")
    archive_state = replace(
        build_initial_app_state(),
        ui_mode="BUSY",
        pending_archive_prepare_request_id=7,
        pending_archive_prepare_request=archive_request,
    )
    archive_result = reduce_app_state(
        archive_state,
        ArchivePreparationFailed(request_id=7, message="archive preparation failed"),
    ).state

    zip_request = CreateZipArchiveRequest(
        source_paths=("/tmp/source.txt",),
        destination_path="/tmp/output.zip",
        root_dir="/tmp",
    )
    zip_state = replace(
        build_initial_app_state(),
        ui_mode="BUSY",
        pending_zip_compress_prepare_request_id=8,
        pending_zip_compress_prepare_request=zip_request,
    )
    zip_result = reduce_app_state(
        zip_state,
        ZipCompressPreparationFailed(request_id=8, message="zip preparation failed"),
    ).state

    for result, request in (
        (archive_result, archive_request),
        (zip_result, zip_request),
    ):
        assert result.notification is not None
        assert result.notification.action == NotificationAction(
            action_id="notification.retry",
            label="Retry",
            payload=request,
        )
        assert result.notification.auto_dismiss is False


def test_archive_and_zip_retry_reenter_fresh_preparation_paths() -> None:
    archive_request = ExtractArchiveRequest("/tmp/archive.zip", "/tmp/archive")
    archive_state = replace(
        build_initial_app_state(),
        notification=NotificationState(
            level="error",
            message="archive preparation failed",
            action=NotificationAction(
                action_id="notification.retry",
                label="Retry",
                payload=archive_request,
            ),
        ),
        notification_revision=5,
    )
    archive_result = reduce_app_state(
        archive_state,
        ActivateNotificationAction("notification.retry", revision=5),
    )

    zip_request = CreateZipArchiveRequest(
        source_paths=("/tmp/source.txt",),
        destination_path="/tmp/output.zip",
        root_dir="/tmp",
    )
    zip_state = replace(
        build_initial_app_state(),
        notification=NotificationState(
            level="error",
            message="zip preparation failed",
            action=NotificationAction(
                action_id="notification.retry",
                label="Retry",
                payload=zip_request,
            ),
        ),
        notification_revision=6,
    )
    zip_result = reduce_app_state(
        zip_state,
        ActivateNotificationAction("notification.retry", revision=6),
    )

    assert archive_result.effects == (
        RunArchivePreparationEffect(request_id=1, request=archive_request),
    )
    assert archive_result.state.pending_archive_prepare_request == archive_request
    assert zip_result.effects == (
        RunZipCompressPreparationEffect(request_id=1, request=zip_request),
    )
    assert zip_result.state.pending_zip_compress_prepare_request == zip_request


def test_duplicate_retry_reenters_duplicate_preflight_path() -> None:
    request = DuplicateRequest(
        source_paths=("/tmp/source.txt",),
        destination_dir="/tmp",
    )
    state = replace(
        build_initial_app_state(),
        notification=NotificationState(
            level="error",
            message="Duplicate failed",
            action=NotificationAction(
                action_id="notification.retry",
                label="Retry",
                payload=request,
            ),
        ),
        notification_revision=7,
    )

    result = reduce_app_state(
        state,
        ActivateNotificationAction("notification.retry", revision=7),
    )

    assert result.effects == (RunDuplicateEffect(request_id=1, request=request),)
    assert result.state.pending_duplicate_request == request


def test_notification_revision_rejects_stale_timer_and_consumes_current_action() -> None:
    state = replace(
        build_initial_app_state(),
        notification=NotificationState(
            level="info",
            message="Done",
            auto_dismiss=True,
        ),
        notification_revision=7,
    )

    newer = reduce_app_state(
        state,
        SetNotification(
            NotificationState(
                level="info",
                message="Done",
                auto_dismiss=True,
            )
        ),
    ).state
    assert newer.notification_revision == 8
    assert newer.notification == state.notification

    stale = reduce_app_state(newer, DismissNotification(revision=7)).state
    assert stale == newer

    cleared = reduce_app_state(state, DismissNotification(revision=7)).state
    assert cleared.notification is None
    assert cleared.notification_revision == 8


def test_retry_consumes_action_and_uses_existing_paste_effect_path() -> None:
    request = PasteRequest(
        mode="copy",
        source_paths=("/tmp/source.txt",),
        destination_dir="/tmp/destination",
    )
    state = replace(
        build_initial_app_state(),
        notification=NotificationState(
            level="error",
            message="Paste failed",
            action=NotificationAction(
                action_id="notification.retry",
                label="Retry",
                payload=request,
            ),
        ),
        notification_revision=3,
    )

    result = reduce_app_state(
        state,
        ActivateNotificationAction("notification.retry", revision=3),
    )

    assert result.state.notification is None
    assert result.state.pending_paste_request == request
    assert result.effects == (
        RunClipboardPasteEffect(request_id=1, request=request),
    )
    assert result.state.pending_paste_retry_requires_confirmation is True


def test_retry_paste_routes_fresh_conflict_to_confirmation_even_with_overwrite_default() -> None:
    request = PasteRequest(
        mode="copy",
        source_paths=("/tmp/source.txt",),
        destination_dir="/tmp/destination",
    )
    state = replace(
        build_initial_app_state(paste_conflict_action="overwrite"),
        notification=NotificationState(
            level="error",
            message="Paste failed",
            action=NotificationAction(
                action_id="notification.retry",
                label="Retry",
                payload=request,
            ),
        ),
        notification_revision=3,
    )

    retry = reduce_app_state(
        state,
        ActivateNotificationAction("notification.retry", revision=3),
    )
    conflict = PasteConflict(
        source_path="/tmp/source.txt",
        destination_path="/tmp/destination/source.txt",
    )
    prompted = reduce_app_state(
        retry.state,
        ClipboardPasteNeedsResolution(
            request_id=1,
            request=request,
            conflicts=(conflict,),
        ),
    )

    assert prompted.effects == ()
    assert prompted.state.ui_mode == "CONFIRM"
    assert prompted.state.paste_conflict is not None
    assert prompted.state.paste_conflict.first_conflict == conflict
    assert prompted.state.pending_paste_request_id is None
    assert prompted.state.pending_paste_request is None
    assert prompted.state.pending_paste_retry_requires_confirmation is False


def test_command_palette_suggested_uses_the_notification_action_id() -> None:
    state = replace(
        build_initial_app_state(),
        notification=NotificationState(
            level="error",
            message="Paste failed",
            action=NotificationAction(
                action_id="notification.retry",
                label="Retry",
            ),
        ),
        notification_revision=2,
    )
    palette_state = reduce_app_state(state, BeginCommandPalette()).state

    items = get_command_palette_items(palette_state)

    assert items[0].id == "notification.retry"
    assert items[0].category == "Suggested"
    assert items[0].label == "Retry"


def test_search_workspace_suggested_notification_action_remains_executable() -> None:
    state = replace(
        build_initial_app_state(),
        current_path="search://readme?target=files&hidden=false&root=%2Ftmp",
        notification=NotificationState(
            level="error",
            message="Paste failed",
            action=NotificationAction(
                action_id="notification.details",
                label="Details",
            ),
            details=NotificationDetails(
                failure_count=1,
                failures=(
                    NotificationFailureDetail(
                        path="/tmp/source.txt",
                        reason="permission denied",
                    ),
                ),
            ),
        ),
        notification_revision=4,
    )
    palette_state = reduce_app_state(state, BeginCommandPalette()).state

    items = get_command_palette_items(palette_state)
    assert items[0].id == "notification.details"
    assert items[0].enabled is True
    assert items[0].category == "Suggested"

    result = reduce_app_state(palette_state, SubmitCommandPalette())
    assert result.state.ui_mode == "DETAIL"
    assert result.state.notification is None
    assert result.state.notification_details is not None


def test_notification_details_selector_includes_failure_count_paths_and_reasons() -> None:
    state = replace(
        build_initial_app_state(),
        notification_details=NotificationDetails(
            failure_count=1,
            failures=(
                NotificationFailureDetail(
                    path="/tmp/failing.txt",
                    reason="permission denied",
                ),
            ),
        ),
    )

    dialog = select_notification_details_dialog_state(state)

    assert dialog is not None
    assert dialog.lines == (
        "Failures: 1",
        "Path: /tmp/failing.txt",
        "Reason: permission denied",
    )
    assert dialog.options == ("enter close", "esc close")
