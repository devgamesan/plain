"""Command palette and search reducer actions."""

from dataclasses import dataclass

from zivo.models import TextReplacePreviewResult, TextReplaceResult

from .models import (
    FileSearchResultState,
    FindReplaceFieldId,
    GrepReplaceFieldId,
    GrepReplaceSelectedFieldId,
    GrepSearchFieldId,
    GrepSearchResultState,
    ReplaceFieldId,
)


@dataclass(frozen=True)
class BeginFileSearch:
    """Open the command palette in file search mode."""


@dataclass(frozen=True)
class BeginGrepSearch:
    """Open the command palette in grep search mode."""


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
class BeginTextReplace:
    """Open the command palette in text-replace mode for selected files."""

    target_paths: tuple[str, ...]


@dataclass(frozen=True)
class BeginFindAndReplace:
    """Open the command palette in find-and-replace mode."""


@dataclass(frozen=True)
class BeginGrepReplace:
    """Open the command palette in grep-and-replace mode."""


@dataclass(frozen=True)
class BeginGrepReplaceSelected:
    """Open the command palette in grep-and-replace-selected mode."""

    target_paths: tuple[str, ...]


@dataclass(frozen=True)
class BeginSelectedFilesGrep:
    """Open the command palette in selected-files-grep mode."""

    target_paths: tuple[str, ...]


@dataclass(frozen=True)
class SelectedFilesGrepKeywordChanged:
    """Update the keyword for selected-files-grep."""

    keyword: str


@dataclass(frozen=True)
class CycleSelectedFilesGrepField:
    """Cycle between fields in selected-files-grep."""

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
    """Update one find-and-replace input field."""

    field: FindReplaceFieldId
    value: str


@dataclass(frozen=True)
class CycleFindReplaceField:
    """Move focus between find-and-replace input fields."""

    delta: int


@dataclass(frozen=True)
class SetGrepReplaceField:
    """Update one grep-and-replace input field."""

    field: GrepReplaceFieldId
    value: str


@dataclass(frozen=True)
class CycleGrepReplaceField:
    """Move focus between grep-and-replace input fields."""

    delta: int


@dataclass(frozen=True)
class SetGrepReplaceSelectedField:
    """Update one grep-replace-selected input field."""

    field: GrepReplaceSelectedFieldId
    value: str


@dataclass(frozen=True)
class CycleGrepReplaceSelectedField:
    """Move focus between grep-replace-selected input fields."""

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
