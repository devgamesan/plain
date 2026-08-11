"""Command palette and search reducer actions."""

from dataclasses import dataclass

from zivo.models import TextReplacePreviewResult, TextReplaceResult

from .models import (
    FileSearchResultState,
    FindReplaceFieldId,
    GoSourceFilter,
    GrepReplaceFieldId,
    GrepReplaceSelectedFieldId,
    GrepSearchFieldId,
    GrepSearchResultState,
    GrepSearchScope,
    ReplaceFieldId,
    ReplaceScope,
)


@dataclass(frozen=True)
class BeginFileSearch:
    """Open the command palette in file search mode."""


@dataclass(frozen=True)
class BeginGrepSearch:
    """Open the command palette in grep search mode."""

    scope: GrepSearchScope | None = None
    target_paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class BeginHistorySearch:
    """Open the command palette in directory history mode."""


@dataclass(frozen=True)
class BeginBookmarkSearch:
    """Open the command palette in bookmark-list mode."""


@dataclass(frozen=True)
class BeginGoToPath:
    """Open the command palette in go-to-path mode."""


@dataclass(frozen=True)
class BeginGo:
    """Open the unified destination picker."""

    source_filter: GoSourceFilter = "all"


@dataclass(frozen=True)
class BeginTextReplace:
    """Open the command palette in the unified text-replace mode."""

    target_paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class BeginFindAndReplace:
    """Legacy action retained while callers migrate to BeginTextReplace."""


@dataclass(frozen=True)
class BeginGrepReplace:
    """Legacy action retained while callers migrate to BeginTextReplace."""


@dataclass(frozen=True)
class BeginGrepReplaceSelected:
    """Legacy action retained while callers migrate to BeginTextReplace."""

    target_paths: tuple[str, ...]


@dataclass(frozen=True)
class SetGrepSearchScope:
    """Change the scope of the shared content search."""

    scope: GrepSearchScope


@dataclass(frozen=True)
class SetReplaceScope:
    """Change the target scope of the unified text replacement flow."""

    scope: ReplaceScope


@dataclass(frozen=True)
class SetFileSearchTarget:
    """Change the file-search target scope."""

    target: str


@dataclass(frozen=True)
class CycleFileSearchField:
    """Cycle between file-search input fields."""

    delta: int


@dataclass(frozen=True)
class BeginCommandPalette:
    """Open the command palette."""


@dataclass(frozen=True)
class CancelCommandPalette:
    """Close the command palette without running a command."""


@dataclass(frozen=True)
class MoveCommandPaletteCursor:
    """Move the command palette cursor by the provided delta."""

    delta: int


@dataclass(frozen=True)
class SetCommandPaletteQuery:
    """Update the command palette query."""

    query: str


@dataclass(frozen=True)
class SetGrepSearchField:
    """Update one grep-search input field."""

    field: GrepSearchFieldId
    value: str


@dataclass(frozen=True)
class CycleGrepSearchField:
    """Move focus between grep-search input fields."""

    delta: int


@dataclass(frozen=True)
class SetReplaceField:
    """Update one text-replace input field."""

    field: ReplaceFieldId
    value: str


@dataclass(frozen=True)
class CycleReplaceField:
    """Move focus between text-replace input fields."""

    delta: int


@dataclass(frozen=True)
class SetFindReplaceField:
    field: FindReplaceFieldId
    value: str


@dataclass(frozen=True)
class CycleFindReplaceField:
    delta: int


@dataclass(frozen=True)
class SetGrepReplaceField:
    field: GrepReplaceFieldId
    value: str


@dataclass(frozen=True)
class CycleGrepReplaceField:
    delta: int


@dataclass(frozen=True)
class SetGrepReplaceSelectedField:
    field: GrepReplaceSelectedFieldId
    value: str


@dataclass(frozen=True)
class CycleGrepReplaceSelectedField:
    delta: int




@dataclass(frozen=True)
class SubmitCommandPalette:
    """Run the currently selected command palette command."""


@dataclass(frozen=True)
class FileSearchCompleted:
    """Apply completed file-search results to the command palette."""

    request_id: int
    query: str
    results: tuple[FileSearchResultState, ...]
    truncated: bool = False


@dataclass(frozen=True)
class FileSearchResultsUpdated:
    """Apply a partial batch of file-search results."""

    request_id: int
    query: str
    results: tuple[FileSearchResultState, ...]
    truncated: bool = False


@dataclass(frozen=True)
class FileSearchFailed:
    """Apply a terminal file-search failure."""

    request_id: int
    query: str
    message: str
    invalid_query: bool = False


@dataclass(frozen=True)
class GrepSearchCompleted:
    """Apply completed grep-search results to the command palette."""

    request_id: int
    query: str
    results: tuple[GrepSearchResultState, ...]
    truncated: bool = False


@dataclass(frozen=True)
class GrepSearchResultsUpdated:
    """Apply a partial batch of grep-search results."""

    request_id: int
    query: str
    results: tuple[GrepSearchResultState, ...]
    truncated: bool = False


@dataclass(frozen=True)
class GrepSearchFailed:
    """Apply a terminal grep-search failure."""

    request_id: int
    query: str
    message: str
    invalid_query: bool = False


@dataclass(frozen=True)
class TextReplacePreviewCompleted:
    """Apply completed text-replace preview results to the command palette."""

    request_id: int
    result: TextReplacePreviewResult


@dataclass(frozen=True)
class TextReplacePreviewFailed:
    """Apply a terminal text-replace preview failure."""

    request_id: int
    message: str
    invalid_query: bool = False


@dataclass(frozen=True)
class TextReplaceApplied:
    """Apply a completed text replacement."""

    request_id: int
    result: TextReplaceResult


@dataclass(frozen=True)
class TextReplaceApplyFailed:
    """Apply a terminal text-replace execution failure."""

    request_id: int
    message: str


@dataclass(frozen=True)
class OpenGrepResultInEditor:
    """Open the selected grep search result in editor at the specific line."""


@dataclass(frozen=True)
class OpenFindResultInEditor:
    """Open the selected file search result in editor."""


@dataclass(frozen=True)
class OpenGrepResultInGuiEditor:
    """Open the selected grep search result in a GUI editor."""


@dataclass(frozen=True)
class OpenFindResultInGuiEditor:
    """Open the selected file search result in a GUI editor."""


@dataclass(frozen=True)
class OpenSearchWorkspace:
    """Open search results as a virtual workspace."""


@dataclass(frozen=True)
class SaveGrepResults:
    """Save the current grep results to the default text file."""


@dataclass(frozen=True)
class GrepExportCompleted:
    """Notify that the grep export completed successfully."""

    request_id: int
    destination_path: str
    exported_results: int


@dataclass(frozen=True)
class GrepExportFailed:
    """Notify that the grep export failed."""

    request_id: int
    message: str
