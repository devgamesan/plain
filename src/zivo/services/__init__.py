"""Application services and effect orchestration."""

import sys

from zivo.archive_utils import (
    default_extract_destination,
    default_zip_destination,
    detect_archive_format,
    is_supported_archive_path,
    resolve_extract_destination_input,
    resolve_zip_destination_input,
)

from .archive_extract import (
    ArchiveExtractService,
    FakeArchiveExtractService,
    LiveArchiveExtractService,
)
from .archive_list import (
    ArchiveListService,
    FakeArchiveListService,
    LiveArchiveListService,
)
from .attribute_inspection import (
    AttributeInspectionService,
    FakeAttributeInspectionService,
    LiveAttributeInspectionService,
)
from .browser_snapshot import (
    PREVIEW_PERMISSION_DENIED_MESSAGE,
    BrowserSnapshotLoader,
    FakeBrowserSnapshotLoader,
    LiveBrowserSnapshotLoader,
    snapshot_from_app_state,
)
from .clipboard_operations import (
    ClipboardOperationService,
    FakeClipboardOperationService,
    LiveClipboardOperationService,
)
from .config import (
    AppConfigLoader,
    ConfigSaveService,
    LiveConfigSaveService,
    load_app_config,
    render_app_config,
    resolve_config_path,
)
from .directory_size import (
    DirectorySizeService,
    FakeDirectorySizeService,
    LiveDirectorySizeService,
)
from .external_launcher import (
    ExternalLaunchService,
    FakeExternalLaunchService,
    LiveExternalLaunchService,
)
from .file_mutations import (
    FakeFileMutationService,
    FileMutationService,
    LiveFileMutationService,
)
from .file_search import (
    FakeFileSearchService,
    FileSearchService,
    InvalidFileSearchQueryError,
    LiveFileSearchService,
)
from .grep_search import (
    FakeGrepSearchService,
    GrepSearchService,
    InvalidGrepSearchQueryError,
    LiveGrepSearchService,
)
from .logging import (
    LoggingSetupResult,
    configure_file_logging,
    resolve_default_log_path,
)
from .shell_command import (
    FakeShellCommandService,
    LiveShellCommandService,
    ShellCommandService,
)

if sys.platform != "win32":
    from .split_terminal import (
        FakeSplitTerminalService,
        LiveSplitTerminalService,
        SplitTerminalService,
        SplitTerminalSession,
    )
else:
    # Windowsではsplit-terminalサービスを提供しない
    # プロトコルはインポート可能にする
    from .split_terminal import (
        SplitTerminalService,
        SplitTerminalSession,
    )
    FakeSplitTerminalService = None  # type: ignore[misc,assignment]
    LiveSplitTerminalService = None  # type: ignore[misc,assignment]
from .text_replace import (
    FakeTextReplaceService,
    InvalidTextReplaceQueryError,
    LiveTextReplaceService,
    TextReplaceService,
)
from .trash_operations import (
    LinuxTrashService,
    MacOsTrashService,
    TrashService,
    UnsupportedPlatformTrashService,
    resolve_trash_service,
)
from .undo_operations import (
    FakeUndoService,
    LiveUndoService,
    UndoService,
)
from .zip_compress import (
    FakeZipCompressService,
    LiveZipCompressService,
    ZipCompressService,
)

__all__ = [
    "AppConfigLoader",
    "ArchiveExtractService",
    "ArchiveListService",
    "AttributeInspectionService",
    "BrowserSnapshotLoader",
    "ClipboardOperationService",
    "ConfigSaveService",
    "default_zip_destination",
    "DirectorySizeService",
    "ExternalLaunchService",
    "FakeZipCompressService",
    "FileSearchService",
    "GrepSearchService",
    "FakeArchiveExtractService",
    "FakeArchiveListService",
    "FakeAttributeInspectionService",
    "FakeFileMutationService",
    "FakeFileSearchService",
    "FakeGrepSearchService",
    "FakeShellCommandService",
    "FakeDirectorySizeService",
    "InvalidFileSearchQueryError",
    "InvalidGrepSearchQueryError",
    "FakeBrowserSnapshotLoader",
    "FakeClipboardOperationService",
    "FakeExternalLaunchService",
    "FileMutationService",
    "LoggingSetupResult",
    "LiveArchiveExtractService",
    "LiveArchiveListService",
    "LiveAttributeInspectionService",
    "LiveExternalLaunchService",
    "LiveFileSearchService",
    "LiveGrepSearchService",
    "LiveFileMutationService",
    "LiveDirectorySizeService",
    "LiveClipboardOperationService",
    "LiveBrowserSnapshotLoader",
    "PREVIEW_PERMISSION_DENIED_MESSAGE",
    "LiveConfigSaveService",
    "LiveShellCommandService",
    "LiveSplitTerminalService",
    "LiveZipCompressService",
    "FakeSplitTerminalService",
    "SplitTerminalService",
    "SplitTerminalSession",
    "TextReplaceService",
    "configure_file_logging",
    "default_extract_destination",
    "detect_archive_format",
    "is_supported_archive_path",
    "load_app_config",
    "render_app_config",
    "resolve_extract_destination_input",
    "resolve_config_path",
    "resolve_default_log_path",
    "resolve_zip_destination_input",
    "ShellCommandService",
    "snapshot_from_app_state",
    "ZipCompressService",
    "LinuxTrashService",
    "MacOsTrashService",
    "TrashService",
    "UnsupportedPlatformTrashService",
    "resolve_trash_service",
    "FakeUndoService",
    "FakeTextReplaceService",
    "LiveUndoService",
    "InvalidTextReplaceQueryError",
    "LiveTextReplaceService",
    "UndoService",
]
