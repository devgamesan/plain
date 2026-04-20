"""Core UI-level reducer actions."""

from dataclasses import dataclass

from .models import AppState, NotificationState, UiMode


@dataclass(frozen=True)
class InitializeState:
    """Replace the entire app state."""

    state: AppState


@dataclass(frozen=True)
class SetUiMode:
    """Change the current UI mode."""

    mode: UiMode


@dataclass(frozen=True)
class SetPendingKeySequence:
    """Store the currently active multi-key prefix."""

    keys: tuple[str, ...]
    possible_next_keys: tuple[str, ...] = ()


@dataclass(frozen=True)
class ClearPendingKeySequence:
    """Clear the currently active multi-key prefix."""


@dataclass(frozen=True)
class SetNotification:
    """Update the transient notification rendered in the shell."""

    notification: NotificationState | None


@dataclass(frozen=True)
class SetTerminalHeight:
    """Update the stored terminal height."""

    height: int
