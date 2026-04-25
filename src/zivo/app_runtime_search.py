"""Runtime scheduling helpers for search and preview effects."""

import threading
from functools import partial
from typing import Any

from zivo.app_runtime_core import (
    SearchRuntimeConfig,
    TrackingConfig,
    WorkerSpec,
    cancel_active_tracking,
    cancel_timer,
    run_worker,
    set_active_tracking,
)
from zivo.state import (
    LoadBrowserSnapshotEffect,
    LoadChildPaneSnapshotEffect,
    LoadCurrentPaneEffect,
    LoadParentChildEffect,
    LoadTransferPaneEffect,
    RunDirectorySizeEffect,
    RunFileSearchEffect,
    RunGrepSearchEffect,
    RunTextReplaceApplyEffect,
    RunTextReplacePreviewEffect,
)

CHILD_PANE_DEBOUNCE_SECONDS = 0.03
FILE_SEARCH_DEBOUNCE_SECONDS = 0.2
GREP_SEARCH_DEBOUNCE_SECONDS = 0.2

FILE_SEARCH_RUNTIME = SearchRuntimeConfig(
    debounce_seconds=FILE_SEARCH_DEBOUNCE_SECONDS,
    worker_key="file-search",
    timer_attr="_file_search_timer",
    pending_request_attr="pending_file_search_request_id",
    service_attr="_file_search_service",
    tracking=TrackingConfig(
        effect_type=RunFileSearchEffect,
        cancel_event_attr="_active_file_search_cancel_event",
        request_id_attr="_active_file_search_request_id",
    ),
)

GREP_SEARCH_RUNTIME = SearchRuntimeConfig(
    debounce_seconds=GREP_SEARCH_DEBOUNCE_SECONDS,
    worker_key="grep-search",
    timer_attr="_grep_search_timer",
    pending_request_attr="pending_grep_search_request_id",
    service_attr="_grep_search_service",
    tracking=TrackingConfig(
        effect_type=RunGrepSearchEffect,
        cancel_event_attr="_active_grep_search_cancel_event",
        request_id_attr="_active_grep_search_request_id",
    ),
)

DIRECTORY_SIZE_TRACKING = TrackingConfig(
    effect_type=RunDirectorySizeEffect,
    cancel_event_attr="_active_directory_size_cancel_event",
    request_id_attr="_active_directory_size_request_id",
)

CHILD_PANE_TRACKING = TrackingConfig(
    effect_type=LoadChildPaneSnapshotEffect,
    cancel_event_attr="_active_child_pane_cancel_event",
    request_id_attr="_active_child_pane_request_id",
)


def schedule_browser_snapshot(app: Any, effect: LoadBrowserSnapshotEffect) -> None:
    if effect.invalidate_paths:
        app._snapshot_loader.invalidate_directory_listing_cache(effect.invalidate_paths)
    run_worker(
        app,
        effect,
        partial(
            app._snapshot_loader.load_browser_snapshot,
            effect.path,
            effect.cursor_path,
            enable_markitdown_preview=effect.enable_markitdown_preview,
        ),
        WorkerSpec(
            name=f"browser-snapshot:{effect.request_id}",
            group="browser-snapshot",
            description=effect.path,
            exclusive=True,
        ),
    )


def schedule_child_pane_snapshot(app: Any, effect: LoadChildPaneSnapshotEffect) -> None:
    cancel_timer(app, "_child_pane_timer")
    if CHILD_PANE_DEBOUNCE_SECONDS <= 0:
        start_child_pane_snapshot(app, effect)
        return
    timer = app.set_timer(
        CHILD_PANE_DEBOUNCE_SECONDS,
        partial(start_child_pane_snapshot, app, effect),
        name=f"child-pane-snapshot-debounce:{effect.request_id}",
    )
    setattr(app, "_child_pane_timer", timer)


def start_child_pane_snapshot(app: Any, effect: LoadChildPaneSnapshotEffect) -> None:
    setattr(app, "_child_pane_timer", None)
    if app._app_state.pending_child_pane_request_id != effect.request_id:
        return
    cancel_event = threading.Event()
    set_active_tracking(app, CHILD_PANE_TRACKING, effect.request_id, cancel_event)
    loader = partial(
        app._snapshot_loader.load_child_pane_snapshot,
        effect.current_path,
        effect.cursor_path,
        preview_max_bytes=effect.preview_max_bytes,
        enable_markitdown_preview=effect.enable_markitdown_preview,
    )
    if effect.grep_result is not None:
        loader = partial(
            app._snapshot_loader.load_grep_preview,
            effect.current_path,
            effect.grep_result,
            context_lines=effect.grep_context_lines,
            preview_max_bytes=effect.preview_max_bytes,
        )
    run_worker(
        app,
        effect,
        loader,
        WorkerSpec(
            name=f"child-pane-snapshot:{effect.request_id}",
            group="child-pane-snapshot",
            description=effect.cursor_path,
            exclusive=True,
        ),
    )


def schedule_progressive_browser_snapshot(app: Any, effect: LoadCurrentPaneEffect) -> None:
    """Schedule Phase 1 of progressive loading: current pane + minimal parent."""
    if effect.invalidate_paths:
        app._snapshot_loader.invalidate_directory_listing_cache(effect.invalidate_paths)

    run_worker(
        app,
        effect,
        partial(
            app._snapshot_loader.load_current_pane_snapshot,
            effect.path,
            effect.cursor_path,
        ),
        WorkerSpec(
            name=f"progressive-snapshot-phase1:{effect.request_id}",
            group="browser-snapshot",
            description=effect.path,
            exclusive=True,
        ),
    )


def schedule_parent_child_update(app: Any, effect: LoadParentChildEffect) -> None:
    """Schedule Phase 2 of progressive loading: parent + child panes."""
    run_worker(
        app,
        effect,
        partial(
            app._snapshot_loader.load_parent_child_panes,
            effect.path,
            effect.cursor_path,
            effect.current_pane,
            enable_markitdown_preview=effect.enable_markitdown_preview,
        ),
        WorkerSpec(
            name=f"progressive-snapshot-phase2:{effect.request_id}",
            group="browser-snapshot",
            description=effect.path,
            exclusive=True,
        ),
    )


def schedule_transfer_pane_snapshot(app: Any, effect: LoadTransferPaneEffect) -> None:
    if effect.invalidate_paths:
        app._snapshot_loader.invalidate_directory_listing_cache(effect.invalidate_paths)
    run_worker(
        app,
        effect,
        partial(
            app._snapshot_loader.load_current_pane_snapshot,
            effect.path,
            effect.cursor_path,
        ),
        WorkerSpec(
            name=f"transfer-pane-snapshot:{effect.request_id}",
            group=f"transfer-pane-snapshot:{effect.pane_id}",
            description=effect.path,
            exclusive=True,
        ),
    )


def schedule_directory_sizes(app: Any, effect: RunDirectorySizeEffect) -> None:
    cancel_event = threading.Event()
    set_active_tracking(app, DIRECTORY_SIZE_TRACKING, effect.request_id, cancel_event)
    run_worker(
        app,
        effect,
        partial(
            app._directory_size_service.calculate_sizes,
            effect.paths,
            is_cancelled=cancel_event.is_set,
        ),
        WorkerSpec(
            name=f"directory-size:{effect.request_id}",
            group="directory-size",
            description=",".join(effect.paths),
            exclusive=True,
        ),
    )


def schedule_file_search(app: Any, effect: RunFileSearchEffect) -> None:
    schedule_search_effect(app, effect, FILE_SEARCH_RUNTIME)


def start_file_search_worker(app: Any, effect: RunFileSearchEffect) -> None:
    start_search_worker(app, effect, FILE_SEARCH_RUNTIME)


def schedule_grep_search(app: Any, effect: RunGrepSearchEffect) -> None:
    schedule_search_effect(app, effect, GREP_SEARCH_RUNTIME)


def start_grep_search_worker(app: Any, effect: RunGrepSearchEffect) -> None:
    start_search_worker(app, effect, GREP_SEARCH_RUNTIME)


def schedule_text_replace_preview(app: Any, effect: RunTextReplacePreviewEffect) -> None:
    run_worker(
        app,
        effect,
        partial(app._text_replace_service.preview, effect.request),
        WorkerSpec(
            name=f"text-replace-preview:{effect.request_id}",
            group="text-replace-preview",
            description="preview replacement",
            exclusive=True,
        ),
    )


def schedule_text_replace_apply(app: Any, effect: RunTextReplaceApplyEffect) -> None:
    run_worker(
        app,
        effect,
        partial(app._text_replace_service.apply, effect.request),
        WorkerSpec(
            name=f"text-replace-apply:{effect.request_id}",
            group="text-replace-apply",
            description="apply replacement",
            exclusive=True,
        ),
    )


def describe_search_effect(effect: RunFileSearchEffect | RunGrepSearchEffect) -> str:
    if isinstance(effect, RunFileSearchEffect):
        return effect.query
    parts = [effect.query]
    if effect.include_globs:
        parts.append(f"include={','.join(effect.include_globs)}")
    if effect.exclude_globs:
        parts.append(f"exclude={','.join(effect.exclude_globs)}")
    return " | ".join(part for part in parts if part)


def cancel_pending_file_search(app: Any) -> None:
    cancel_pending_search(app, FILE_SEARCH_RUNTIME)


def cancel_file_search_timer(app: Any) -> None:
    cancel_timer(app, FILE_SEARCH_RUNTIME.timer_attr)


def cancel_active_file_search(app: Any) -> None:
    cancel_active_tracking(app, FILE_SEARCH_RUNTIME.tracking)


def cancel_pending_grep_search(app: Any) -> None:
    cancel_pending_search(app, GREP_SEARCH_RUNTIME)


def cancel_grep_search_timer(app: Any) -> None:
    cancel_timer(app, GREP_SEARCH_RUNTIME.timer_attr)


def cancel_active_grep_search(app: Any) -> None:
    cancel_active_tracking(app, GREP_SEARCH_RUNTIME.tracking)


def cancel_pending_directory_size(app: Any) -> None:
    cancel_active_tracking(app, DIRECTORY_SIZE_TRACKING)


def cancel_pending_child_pane(app: Any) -> None:
    cancel_timer(app, "_child_pane_timer")
    cancel_active_tracking(app, CHILD_PANE_TRACKING)


def cancel_pending_search(app: Any, config: SearchRuntimeConfig) -> None:
    cancel_timer(app, config.timer_attr)
    cancel_active_tracking(app, config.tracking)


def schedule_search_effect(
    app: Any,
    effect: RunFileSearchEffect | RunGrepSearchEffect,
    config: SearchRuntimeConfig,
) -> None:
    cancel_timer(app, config.timer_attr)
    timer = app.set_timer(
        config.debounce_seconds,
        partial(start_search_worker, app, effect, config),
        name=f"{config.worker_key}-debounce:{effect.request_id}",
    )
    setattr(app, config.timer_attr, timer)


def start_search_worker(
    app: Any,
    effect: RunFileSearchEffect | RunGrepSearchEffect,
    config: SearchRuntimeConfig,
) -> None:
    setattr(app, config.timer_attr, None)
    if getattr(app._app_state, config.pending_request_attr) != effect.request_id:
        return
    cancel_event = threading.Event()
    set_active_tracking(app, config.tracking, effect.request_id, cancel_event)
    service = getattr(app, config.service_attr)
    search_kwargs = {
        "show_hidden": effect.show_hidden,
        "is_cancelled": cancel_event.is_set,
    }

    # ファイル検索の場合のみ max_results を追加
    if isinstance(effect, RunFileSearchEffect):
        search_kwargs["max_results"] = app._app_state.config.file_search.max_results

    if isinstance(effect, RunGrepSearchEffect):
        search_kwargs["include_globs"] = effect.include_globs
        search_kwargs["exclude_globs"] = effect.exclude_globs
    run_worker(
        app,
        effect,
        partial(
            service.search,
            effect.root_path,
            effect.query,
            **search_kwargs,
        ),
        WorkerSpec(
            name=f"{config.worker_key}:{effect.request_id}",
            group=config.worker_key,
            description=describe_search_effect(effect),
            exclusive=True,
        ),
    )
