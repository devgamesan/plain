"""Reducer for file preview actions."""

import logging
from dataclasses import replace
from typing import Callable

from peneo.models.shell_data import NotificationLevel

from .actions import (
    Action,
    FilePreviewFailed,
    FilePreviewLoaded,
    RequestFilePreview,
)
from .effects import LoadFilePreviewEffect, ReduceResult
from .models import AppState, FilePreviewState, NotificationState
from .reducer_common import done

logger = logging.getLogger(__name__)


def handle_preview_action(
    state: AppState,
    action: Action,
    reduce_fn: Callable[[AppState, Action], ReduceResult],
) -> ReduceResult | None:
    """Handle file preview actions.

    Args:
        state: Current application state
        action: Action to handle
        reduce_fn: Main reducer function for nested reductions

    Returns:
        ReduceResult if action was handled, None otherwise
    """
    if isinstance(action, RequestFilePreview):
        return _handle_request_file_preview(state, action)

    if isinstance(action, FilePreviewLoaded):
        return _handle_file_preview_loaded(state, action)

    if isinstance(action, FilePreviewFailed):
        return _handle_file_preview_failed(state, action)

    return None


def _handle_request_file_preview(state: AppState, action: RequestFilePreview) -> ReduceResult:
    """Handle a file preview request.

    Args:
        state: Current application state
        action: RequestFilePreview action

    Returns:
        ReduceResult with LoadFilePreviewEffect
    """
    # Check if preview is enabled in config
    if not state.config.preview.enabled:
        return done(state)

    # Check if the path is different from current preview
    if state.file_preview.path == action.path:
        # Already loaded or loading
        return done(state)

    # Create request ID
    request_id = state.next_request_id

    # Update state to show loading
    next_state = replace(
        state,
        file_preview=FilePreviewState(path=action.path, content=None, error=None),
        pending_file_preview_request_id=request_id,
        next_request_id=request_id + 1,
    )

    # Create effect to load preview
    effect = LoadFilePreviewEffect(
        request_id=request_id,
        path=action.path,
        max_size=state.config.preview.max_size_bytes,
        max_lines=state.config.preview.max_lines,
    )

    return done(next_state, effect)


def _handle_file_preview_loaded(state: AppState, action: FilePreviewLoaded) -> ReduceResult:
    """Handle a successful file preview load.

    Args:
        state: Current application state
        action: FilePreviewLoaded action

    Returns:
        ReduceResult with updated preview content
    """
    # Check if this is the current request
    if state.pending_file_preview_request_id != action.request_id:
        logger.debug(
            "Ignoring stale file preview load: request_id=%d (expected %d)",
            action.request_id,
            state.pending_file_preview_request_id,
        )
        return done(state)

    # Update preview content
    next_state = replace(
        state,
        file_preview=FilePreviewState(path=action.path, content=action.content, error=None),
        pending_file_preview_request_id=None,
    )

    return done(next_state)


def _handle_file_preview_failed(state: AppState, action: FilePreviewFailed) -> ReduceResult:
    """Handle a failed file preview load.

    Args:
        state: Current application state
        action: FilePreviewFailed action

    Returns:
        ReduceResult with error notification
    """
    # Check if this is the current request
    if state.pending_file_preview_request_id != action.request_id:
        logger.debug(
            "Ignoring stale file preview failure: request_id=%d (expected %d)",
            action.request_id,
            state.pending_file_preview_request_id,
        )
        return done(state)

    # Update preview state with error
    next_state = replace(
        state,
        file_preview=FilePreviewState(path=action.path, content=None, error=action.message),
        pending_file_preview_request_id=None,
        notification=NotificationState(
            level=NotificationLevel.WARNING,
            message=f"Failed to load preview: {action.message}",
        ),
    )

    return done(next_state)
