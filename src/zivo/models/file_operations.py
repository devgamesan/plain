"""Shared models for filesystem mutations."""

from dataclasses import dataclass
from typing import Literal

ClipboardOperationMode = Literal["copy", "cut"]
ConflictResolution = Literal["overwrite", "skip", "rename"]
CreateKind = Literal["file", "dir"]
DeleteMode = Literal["trash", "permanent"]
MutationResultLevel = Literal["info", "warning", "error"]
ArchiveFormat = Literal["zip", "tar", "tar.gz", "tar.bz2", "gz", "bz2"]
FileMutationOperation = Literal["rename", "create", "delete"]
UndoOperationKind = Literal["rename", "paste_copy", "paste_cut", "trash_delete"]


@dataclass(frozen=True)
class PasteRequest:
    """A request to paste clipboard entries into a destination directory."""

    mode: ClipboardOperationMode
    source_paths: tuple[str, ...]
    destination_dir: str
    conflict_resolution: ConflictResolution | None = None


@dataclass(frozen=True)
class PasteConflict:
    """A destination path that would collide during paste."""

    source_path: str
    destination_path: str


@dataclass(frozen=True)
class PasteFailure:
    """A single source item that could not be pasted."""

    source_path: str
    destination_path: str
    message: str


@dataclass(frozen=True)
class PasteAppliedChange:
    """A single source item that was successfully pasted."""

    source_path: str
    destination_path: str


@dataclass(frozen=True)
class PasteConflictPrompt:
    """A paste request that needs an explicit conflict resolution."""

    request: PasteRequest
    conflicts: tuple[PasteConflict, ...]


@dataclass(frozen=True)
class PasteSummary:
    """Terminal result of a paste operation."""

    mode: ClipboardOperationMode
    destination_dir: str
    total_count: int
    success_count: int
    skipped_count: int
    failures: tuple[PasteFailure, ...] = ()
    conflict_resolution: ConflictResolution | None = None
    overwrote_count: int = 0

    @property
    def failure_count(self) -> int:
        """Return the number of failed items."""

        return len(self.failures)


@dataclass(frozen=True)
class PasteExecutionResult:
    """Completed execution payload returned from the clipboard service."""

    summary: PasteSummary
    applied_changes: tuple[PasteAppliedChange, ...] = ()


@dataclass(frozen=True)
class TrashRestoreRecord:
    """Metadata required to restore a trashed entry back to its original path."""

    original_path: str
    trashed_path: str
    metadata_path: str


@dataclass(frozen=True)
class RenameRequest:
    """A request to rename a single path within its current directory."""

    source_path: str
    new_name: str


@dataclass(frozen=True)
class CreatePathRequest:
    """A request to create a file or directory in a parent directory."""

    parent_dir: str
    name: str
    kind: CreateKind


@dataclass(frozen=True)
class DeleteRequest:
    """A request to trash or permanently delete one or more paths."""

    paths: tuple[str, ...]
    mode: DeleteMode = "trash"


FileMutationRequest = RenameRequest | CreatePathRequest | DeleteRequest


@dataclass(frozen=True)
class TextReplaceRequest:
    """A request to preview or apply text replacement across files."""

    paths: tuple[str, ...]
    find_text: str
    replace_text: str


@dataclass(frozen=True)
class TextReplacePreviewEntry:
    """Preview details for a single file that would be changed."""

    path: str
    diff_text: str
    match_count: int
    first_match_line_number: int
    first_match_before: str
    first_match_after: str


@dataclass(frozen=True)
class TextReplacePreviewResult:
    """Preview payload returned before applying text replacement."""

    request: TextReplaceRequest
    changed_entries: tuple[TextReplacePreviewEntry, ...]
    total_match_count: int
    diff_text: str = ""
    skipped_paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class TextReplaceResult:
    """Completed text replacement payload returned from the service."""

    request: TextReplaceRequest
    changed_paths: tuple[str, ...]
    total_match_count: int
    message: str
    level: MutationResultLevel = "info"
    skipped_paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExtractArchiveRequest:
    """A request to extract a supported archive into a destination directory."""

    source_path: str
    destination_path: str


@dataclass(frozen=True)
class ExtractArchiveConflict:
    """A destination path that already exists before extraction begins."""

    archive_path: str
    destination_path: str


@dataclass(frozen=True)
class ExtractArchivePreparationResult:
    """Preflight archive scan details returned before extraction begins."""

    request: ExtractArchiveRequest
    format: ArchiveFormat
    total_entries: int
    conflicts: tuple[ExtractArchiveConflict, ...] = ()


@dataclass(frozen=True)
class ExtractArchiveResult:
    """Completed extraction payload returned from the archive service."""

    destination_path: str
    extracted_entries: int
    total_entries: int
    message: str
    level: MutationResultLevel = "info"


@dataclass(frozen=True)
class CreateZipArchiveRequest:
    """A request to compress one or more paths into a zip archive."""

    source_paths: tuple[str, ...]
    destination_path: str
    root_dir: str


@dataclass(frozen=True)
class CreateZipArchivePreparationResult:
    """Preflight zip-compression details returned before execution begins."""

    request: CreateZipArchiveRequest
    total_entries: int
    destination_exists: bool = False


@dataclass(frozen=True)
class CreateZipArchiveResult:
    """Completed zip-compression payload returned from the zip service."""

    destination_path: str
    archived_entries: int
    total_entries: int
    message: str
    level: MutationResultLevel = "info"


@dataclass(frozen=True)
class FileMutationResult:
    """Completed execution payload returned from the file mutation service."""

    path: str | None
    message: str
    level: MutationResultLevel = "info"
    removed_paths: tuple[str, ...] = ()
    operation: FileMutationOperation = "create"
    source_path: str | None = None
    delete_mode: DeleteMode | None = None
    trash_records: tuple[TrashRestoreRecord, ...] = ()


@dataclass(frozen=True)
class UndoDeletePathStep:
    """Undo step that removes a created path."""

    path: str


@dataclass(frozen=True)
class UndoMovePathStep:
    """Undo step that moves a path back to a previous location."""

    source_path: str
    destination_path: str


@dataclass(frozen=True)
class UndoRestoreTrashStep:
    """Undo step that restores an item from trash metadata."""

    record: TrashRestoreRecord


UndoStep = UndoDeletePathStep | UndoMovePathStep | UndoRestoreTrashStep


@dataclass(frozen=True)
class UndoEntry:
    """A single undoable file operation."""

    kind: UndoOperationKind
    steps: tuple[UndoStep, ...]


@dataclass(frozen=True)
class UndoResult:
    """Completed execution payload returned from the undo service."""

    path: str | None
    message: str
    level: MutationResultLevel = "info"
    removed_paths: tuple[str, ...] = ()
