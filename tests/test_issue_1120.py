from dataclasses import replace

from tests.support.paths import TEST_PROJECT_ROOT
from zivo.models import UndoDeletePathStep, UndoEntry
from zivo.services import PREVIEW_PERMISSION_DENIED_MESSAGE, LiveBrowserSnapshotLoader
from zivo.state import (
    NotificationAction,
    NotificationDetails,
    NotificationFailureDetail,
    PaneState,
    build_initial_app_state,
    dispatch_key_input,
    reduce_app_state,
    select_notification_details_dialog_state,
    select_shell_data,
)
from zivo.state.actions import ActivateNotificationAction, ToggleHiddenFiles
from zivo.state.input_dialogs import dispatch_detail_input
from zivo.state.models import DirectoryEntryState


def test_parent_pane_status_distinguishes_root_loading_permission_and_hidden_items() -> None:
    base = build_initial_app_state()

    root = replace(
        base,
        current_path="/",
        current_pane=PaneState(directory_path="/", entries=()),
        parent_pane=PaneState(directory_path="/", entries=()),
    )
    assert select_shell_data(root).parent_pane_status is not None
    assert select_shell_data(root).parent_pane_status.kind == "no_parent"

    loading = replace(
        base,
        parent_pane=PaneState(directory_path="/tmp", entries=()),
        parent_pane_loading=True,
    )
    assert select_shell_data(loading).parent_pane_status.kind == "loading"

    permission_denied = replace(
        base,
        parent_pane=PaneState(
            directory_path="/tmp",
            entries=(),
            preview_message=PREVIEW_PERMISSION_DENIED_MESSAGE,
            preview_reason="permission_denied",
        ),
    )
    assert select_shell_data(permission_denied).parent_pane_status.kind == "permission_denied"

    hidden_parent = replace(
        base,
        parent_pane=PaneState(
            directory_path="/tmp",
            entries=(
                DirectoryEntryState("/tmp/.hidden", ".hidden", "dir", hidden=True),
            ),
        ),
        show_hidden=False,
    )
    assert select_shell_data(hidden_parent).parent_pane_status.kind == "no_visible"


def test_parent_pane_keeps_cached_entries_visible_while_loading() -> None:
    state = replace(build_initial_app_state(), parent_pane_loading=True)

    shell = select_shell_data(state)

    assert shell.parent_entries
    assert shell.parent_pane_status is None
    assert shell.parent_heading.endswith(" · loading")


def test_no_visible_items_offers_existing_hidden_file_action() -> None:
    path = TEST_PROJECT_ROOT + '/.hidden'
    state = replace(
        build_initial_app_state(),
        current_pane=PaneState(
            directory_path=TEST_PROJECT_ROOT,
            entries=(DirectoryEntryState(path, ".hidden", "file", hidden=True),),
        ),
        show_hidden=False,
    )

    status = select_shell_data(state).current_pane_status
    assert status is not None
    assert status.actions[0].action_id == "toggle_hidden"
    assert status.actions[0].shortcut == "."

    actions = dispatch_key_input(state, key=".", character=".")
    assert actions[-1] == ToggleHiddenFiles()


def test_details_recovery_reuses_undo_action_and_keeps_close_options() -> None:
    entry = UndoEntry(
        kind="paste_copy",
        steps=(UndoDeletePathStep(path="/tmp/copied.txt"),),
    )
    state = replace(
        build_initial_app_state(),
        notification_details=NotificationDetails(
            failure_count=1,
            failures=(
                NotificationFailureDetail(
                    path="/tmp/failed.txt",
                    reason="permission denied",
                ),
            ),
            recovery_action=NotificationAction(
                action_id="notification.undo",
                label="Undo completed items",
                payload=entry,
            ),
        ),
        notification_revision=7,
        undo_stack=(entry,),
        ui_mode="DETAIL",
    )

    dialog = select_notification_details_dialog_state(state)
    assert dialog is not None
    assert dialog.options == (
        "z Undo completed items",
        "enter close",
        "esc close",
    )
    assert dialog.recovery_action_id == "notification.undo"

    detail_actions = dispatch_detail_input(state, key="z", character="z")
    assert detail_actions[-1] == ActivateNotificationAction(
        "notification.undo",
        revision=7,
    )

    result = reduce_app_state(
        state,
        ActivateNotificationAction("notification.undo", revision=7),
    )
    assert result.state.pending_undo_entry == entry
    assert result.state.notification_details is None
    assert result.state.ui_mode == "BUSY"


def test_parent_snapshot_preserves_permission_denied_as_parent_state(tmp_path) -> None:
    project = tmp_path / "project"
    project.mkdir()

    class StubFilesystem:
        def list_directory_summary(self, path: str):
            if path == str(tmp_path):
                raise PermissionError("blocked")
            return ()

        def list_directory(self, path: str):
            return self.list_directory_summary(path)

    loader = LiveBrowserSnapshotLoader(filesystem=StubFilesystem())
    snapshot = loader.load_browser_snapshot(str(project))
    parent, child = loader.load_parent_child_panes(
        str(project),
        None,
        PaneState(directory_path=str(project), entries=()),
    )

    assert child.entries == ()
    assert snapshot.parent_pane.preview_reason == "permission_denied"
    assert parent.preview_reason == "permission_denied"
    assert parent.preview_message == PREVIEW_PERMISSION_DENIED_MESSAGE
