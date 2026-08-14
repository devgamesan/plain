import asyncio
from dataclasses import replace

import pytest

from zivo import create_app
from zivo.models import ExternalLaunchRequest
from zivo.services import FakeBrowserSnapshotLoader, FakeExternalLaunchService
from zivo.state import (
    BrowserSnapshot,
    DirectoryEntryState,
    NotificationState,
    PaneState,
    RunExternalLaunchEffect,
    build_initial_app_state,
    reduce_app_state,
    select_shell_data,
)
from zivo.state.actions import OpenPreviewWithDefaultApp
from zivo.ui import ChildPane


def _fallback_state(path: str, *, reason: str = "unsupported"):
    state = build_initial_app_state()
    entry = DirectoryEntryState(path, path.rsplit("/", 1)[-1], "file")
    return replace(
        state,
        current_pane=replace(
            state.current_pane,
            entries=(entry,),
            cursor_path=path,
        ),
        child_pane=PaneState(
            directory_path=state.current_path,
            entries=(),
            mode="preview",
            preview_path=path,
            preview_message="Preview unavailable",
            preview_reason=reason,
        ),
    )


@pytest.mark.parametrize(
    ("reason", "action_id", "label"),
    (
        ("dependency_missing", "open_preview_default_app", "Open with default app"),
        ("unsupported", "open_preview_default_app", "Open with default app"),
        ("error", "open_preview_default_app", "Open with default app"),
        ("timeout", "open_preview_default_app", "Open with default app"),
        ("resource_limit", "open_preview_default_app", "Open with default app"),
        ("no_text_content", "open_preview_default_app", "Open with default app"),
        ("permission_denied", "show_attributes", "Show attributes"),
        ("cancelled", "show_attributes", "Show attributes"),
    ),
)
def test_preview_fallback_exposes_one_reason_specific_action(reason, action_id, label) -> None:
    state = _fallback_state(f"{build_initial_app_state().current_path}/preview.bin", reason=reason)

    status = select_shell_data(state).child_pane.status

    assert status is not None
    assert len(status.actions) == 1
    assert status.actions[0].action_id == action_id
    assert status.actions[0].label == label
    assert status.actions[0].target_path == state.child_pane.preview_path


def test_preview_fallback_describes_no_text_content() -> None:
    state = _fallback_state(
        f"{build_initial_app_state().current_path}/scan.pdf",
        reason="no_text_content",
    )

    status = select_shell_data(state).child_pane.status

    assert status is not None
    assert status.title == "No text content found"
    assert status.detail == "This may be a scanned or image-only document"


def test_archive_listing_fallback_does_not_offer_file_open() -> None:
    path = f"{build_initial_app_state().current_path}/broken.zip"
    state = _fallback_state(path)
    shell = select_shell_data(state).child_pane

    assert shell.status is not None
    assert shell.status.actions[0].action_id == "show_attributes"


def test_open_preview_default_app_reuses_existing_external_launch_effect() -> None:
    path = f"{build_initial_app_state().current_path}/preview.bin"
    state = _fallback_state(path)

    result = reduce_app_state(state, OpenPreviewWithDefaultApp(path))

    assert result.effects == (
        RunExternalLaunchEffect(
            request_id=state.next_request_id,
            request=ExternalLaunchRequest(kind="open_file", path=path),
        ),
    )
    assert result.state.notification is None


@pytest.mark.asyncio
async def test_inline_preview_action_dispatches_existing_open_file_request() -> None:
    path = "/tmp/zivo-issue-1186"
    target = f"{path}/preview.bin"
    entry = DirectoryEntryState(target, "preview.bin", "file")
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: BrowserSnapshot(
                current_path=path,
                parent_pane=PaneState(
                    directory_path="/tmp",
                    entries=(DirectoryEntryState(path, "zivo-issue-1186", "dir"),),
                    cursor_path=path,
                ),
                current_pane=PaneState(
                    directory_path=path,
                    entries=(entry,),
                    cursor_path=target,
                ),
                child_pane=PaneState(
                    directory_path=path,
                    entries=(),
                    mode="preview",
                    preview_path=target,
                    preview_message="Preview unavailable for this file type",
                    preview_reason="unsupported",
                ),
            )
        }
    )
    launch_service = FakeExternalLaunchService()
    app = create_app(
        snapshot_loader=loader,
        external_launch_service=launch_service,
        initial_path=path,
    )

    async with app.run_test():
        for _ in range(100):
            if (
                app.app_state.current_path == path
                and app.app_state.child_pane.preview_path == target
            ):
                break
            await asyncio.sleep(0.01)
        else:
            raise AssertionError("preview snapshot did not load")

        await app.on_child_pane_action_clicked(
            ChildPane.ActionClicked("open_preview_default_app", target)
        )
        for _ in range(100):
            if launch_service.executed_requests:
                break
            await asyncio.sleep(0.01)
        else:
            raise AssertionError("external launch was not requested")

    assert launch_service.executed_requests == [
        ExternalLaunchRequest(kind="open_file", path=target)
    ]


def test_open_preview_default_app_rejects_stale_preview_target() -> None:
    path = f"{build_initial_app_state().current_path}/preview.bin"
    state = _fallback_state(path)
    state = replace(
        state,
        current_pane=replace(
            state.current_pane,
            cursor_path=f"{state.current_path}/other.bin",
        ),
    )

    result = reduce_app_state(state, OpenPreviewWithDefaultApp(path))

    assert result.effects == ()
    assert result.state.notification == NotificationState(
        level="warning",
        message="Preview target changed; select the file and try again",
    )


@pytest.mark.parametrize(
    "path,kind,message",
    (
        ("/tmp/zivo-preview-directory", "dir", "This preview action is only available for files"),
        ("/tmp/zivo-preview.zip", "file", "This preview action is only available for files"),
    ),
)
def test_open_preview_default_app_rejects_directories_and_archive_listings(
    path: str,
    kind: str,
    message: str,
) -> None:
    state = build_initial_app_state()
    entry = DirectoryEntryState(path, path.rsplit("/", 1)[-1], kind)  # type: ignore[arg-type]
    state = replace(
        state,
        current_pane=replace(state.current_pane, entries=(entry,), cursor_path=path),
        child_pane=replace(
            state.child_pane,
            mode="preview",
            preview_path=path,
            preview_reason="unsupported",
        ),
    )

    result = reduce_app_state(state, OpenPreviewWithDefaultApp(path))

    assert result.effects == ()
    assert result.state.notification == NotificationState(level="warning", message=message)
