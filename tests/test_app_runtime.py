from peneo.app_runtime import complete_worker_actions, failed_worker_actions
from peneo.models import AppConfig
from peneo.services import InvalidFileSearchQueryError
from peneo.state import (
    BrowserSnapshot,
    BrowserSnapshotLoaded,
    ConfigSaveCompleted,
    DirectoryEntryState,
    DirectorySizesLoaded,
    FileSearchFailed,
    LoadBrowserSnapshotEffect,
    PaneState,
    RunConfigSaveEffect,
    RunDirectorySizeEffect,
    RunFileSearchEffect,
)


def test_complete_worker_actions_maps_browser_snapshot_load() -> None:
    snapshot = BrowserSnapshot(
        current_path="/tmp/project",
        parent_pane=PaneState(
            directory_path="/tmp",
            entries=(DirectoryEntryState("/tmp/project", "project", "dir"),),
        ),
        current_pane=PaneState(
            directory_path="/tmp/project",
            entries=(DirectoryEntryState("/tmp/project/README.md", "README.md", "file"),),
            cursor_path="/tmp/project/README.md",
        ),
        child_pane=PaneState(directory_path="/tmp/project", entries=()),
    )

    actions = complete_worker_actions(
        LoadBrowserSnapshotEffect(
            request_id=7,
            path="/tmp/project",
            cursor_path="/tmp/project/README.md",
            blocking=True,
        ),
        snapshot,
    )

    assert actions == (
        BrowserSnapshotLoaded(
            request_id=7,
            snapshot=snapshot,
            blocking=True,
        ),
    )


def test_complete_worker_actions_maps_directory_size_result() -> None:
    actions = complete_worker_actions(
        RunDirectorySizeEffect(
            request_id=11,
            paths=("/tmp/project/docs",),
        ),
        ((("/tmp/project/docs", 1234),), ()),
    )

    assert actions == (
        DirectorySizesLoaded(
            request_id=11,
            sizes=(("/tmp/project/docs", 1234),),
            failures=(),
        ),
    )


def test_complete_worker_actions_maps_config_save_result() -> None:
    config = AppConfig()

    actions = complete_worker_actions(
        RunConfigSaveEffect(
            request_id=5,
            path="/tmp/config.toml",
            config=config,
        ),
        "/tmp/config.toml",
    )

    assert actions == (
        ConfigSaveCompleted(
            request_id=5,
            path="/tmp/config.toml",
            config=config,
        ),
    )


def test_failed_worker_actions_marks_invalid_file_search_queries() -> None:
    actions = failed_worker_actions(
        RunFileSearchEffect(
            request_id=13,
            root_path="/tmp/project",
            query="re:[",
            show_hidden=False,
        ),
        InvalidFileSearchQueryError("unterminated character set"),
    )

    assert actions == (
        FileSearchFailed(
            request_id=13,
            query="re:[",
            message="unterminated character set",
            invalid_query=True,
        ),
    )
