"""Shared models for filesystem mutations."""

from dataclasses import dataclass
from typing import Literal

ClipboardOperationMode = Literal["copy", "cut"]
ConflictResolution = Literal["overwrite", "skip", "rename"]
CreateKind = Literal["file", "dir"]
MutationResultLevel = Literal["info", "warning", "error"]
ArchiveFormat = Literal["zip", "tar", "tar.gz", "tar.bz2"]


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

    @property
    def failure_count(self) -> int:
        """Return the number of failed items."""

        return len(self.failures)


@dataclass(frozen=True)
class PasteExecutionResult:
    """Completed execution payload returned from the clipboard service."""

    summary: PasteSummary


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
class TrashDeleteRequest:
    """A request to move one or more paths into the OS trash."""

    paths: tuple[str, ...]


FileMutationRequest = RenameRequest | CreatePathRequest | TrashDeleteRequest


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
class FileMutationResult:
    """Completed execution payload returned from the file mutation service."""

    path: str | None
    message: str
    level: MutationResultLevel = "info"
    removed_paths: tuple[str, ...] = ()
