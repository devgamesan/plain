"""Shared setup for test_state_reducer_palette_replace tests."""

# Test support re-exports model and action types used by split modules.
# ruff: noqa: F401

from dataclasses import replace

from tests.support.state import reduce_state
from zivo.models import (
    TextReplacePreviewEntry,
    TextReplacePreviewResult,
    TextReplaceRequest,
    TextReplaceResult,
)
from zivo.state import (
    CommandPaletteState,
    DirectoryEntryState,
    FileSearchResultState,
    GrepSearchResultState,
    LoadCurrentPaneEffect,
    NotificationState,
    PaneState,
    ReplacePreviewPaletteState,
    ReplacePreviewResultState,
    RunFileSearchEffect,
    RunGrepSearchEffect,
    RunTextReplaceApplyEffect,
    RunTextReplacePreviewEffect,
    build_initial_app_state,
    reduce_app_state,
)
from zivo.state.actions import (
    BeginCommandPalette,
    BeginFindAndReplace,
    BeginGrepReplace,
    BeginGrepReplaceSelected,
    BeginReplaceFromSearchResults,
    BeginTextReplace,
    CancelCommandPalette,
    ConfirmReplaceTargets,
    CycleFindReplaceField,
    CycleReplaceField,
    FileSearchCompleted,
    GrepSearchCompleted,
    MoveCommandPaletteCursor,
    SetCommandPaletteQuery,
    SetFindReplaceField,
    SetGrepReplaceField,
    SetGrepReplaceSelectedField,
    SetReplaceField,
    SetReplaceScope,
    SubmitCommandPalette,
    TextReplaceApplied,
    TextReplaceApplyFailed,
    TextReplacePreviewCompleted,
    TextReplacePreviewFailed,
)
from zivo.state.reducer_common import browser_snapshot_invalidation_paths


def _reduce_state(state, action):
    return reduce_state(state, action)


def _viewport_test_entries(
    path: str,
    count: int,
    *,
    hidden_indexes: frozenset[int] = frozenset(),
) -> tuple[DirectoryEntryState, ...]:
    return tuple(
        DirectoryEntryState(
            f"{path}/item_{index:02d}",
            f"item_{index:02d}",
            "file",
            hidden=index in hidden_indexes,
        )
        for index in range(count)
    )


