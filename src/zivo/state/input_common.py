"""Shared helpers for keyboard input dispatchers."""

from collections.abc import Callable
from dataclasses import dataclass

from zivo.windows_paths import paths_equal

from .actions import Action, SetNotification
from .models import AppState, DirectoryEntryState, NotificationState
from .selectors import select_visible_current_entry_states

DispatchedActions = tuple[Action, ...]


@dataclass(frozen=True)
class BrowsingCtx:
    """Precomputed context shared while dispatching browsing-mode input."""

    visible_paths: tuple[str, ...]
    cursor_entry: DirectoryEntryState | None
    target_paths: tuple[str, ...]
    filter_is_active: bool


BrowsingHandler = Callable[[AppState, BrowsingCtx], DispatchedActions]


def visible_paths(state: AppState) -> tuple[str, ...]:
    return tuple(entry.path for entry in select_visible_current_entry_states(state))


def current_entry(state: AppState) -> DirectoryEntryState | None:
    cursor_path = state.current_pane.cursor_path
    for entry in select_visible_current_entry_states(state):
        if paths_equal(entry.path, cursor_path):
            return entry
    return None


def supported(*actions: Action) -> DispatchedActions:
    return (SetNotification(None), *actions)


def warn(message: str) -> DispatchedActions:
    return (SetNotification(NotificationState(level="warning", message=message)),)
