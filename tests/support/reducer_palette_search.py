"""Shared setup for test_state_reducer_palette_search tests."""

# Test support re-exports model and action types used by split modules.
# ruff: noqa: F401

from dataclasses import replace

import pytest

from tests.support.state import reduce_state
from zivo.models import (
    ExternalLaunchRequest,
)
from zivo.state import (
    CommandPaletteState,
    DirectoryEntryState,
    FileSearchResultState,
    GrepSearchPaletteState,
    GrepSearchResultState,
    LoadBrowserSnapshotEffect,
    LoadChildPaneSnapshotEffect,
    NotificationState,
    PaneState,
    RunDirectorySizeEffect,
    RunExternalLaunchEffect,
    RunFileSearchEffect,
    RunGrepSearchEffect,
    build_initial_app_state,
    reduce_app_state,
)
from zivo.state.actions import (
    BeginCommandPalette,
    BeginFileSearch,
    BeginGrepSearch,
    CancelCommandPalette,
    FileSearchCompleted,
    FileSearchFailed,
    FileSearchResultsUpdated,
    GrepSearchCompleted,
    GrepSearchFailed,
    GrepSearchResultsUpdated,
    OpenFindResultInEditor,
    OpenFindResultInGuiEditor,
    OpenGrepResultInEditor,
    OpenGrepResultInGuiEditor,
    OpenSearchWorkspace,
    SetCommandPaletteQuery,
    SetFileSearchField,
    SetFileSearchTarget,
    SetGrepSearchField,
    SetGrepSearchScope,
    SubmitCommandPalette,
)


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


