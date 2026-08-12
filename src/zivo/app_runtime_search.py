"""Runtime scheduling helpers for search and preview effects."""

import threading
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any

from textual.css.query import NoMatches

from zivo.app_runtime_core import (
    SearchRuntimeConfig,
    TrackingConfig,
    WorkerSpec,
    cancel_active_tracking,
    cancel_timer,
    run_worker,
    set_active_tracking,
    start_foreground_operation,
)
from zivo.app_runtime_execution import report_foreground_operation_progress, report_search_results
from zivo.models.config import DEFAULT_SEARCH_MAX_RESULTS
from zivo.services import GoPathCompletionResult
from zivo.state import (
    LoadBrowserSnapshotEffect,
    LoadChildPaneSnapshotEffect,
    LoadCurrentPaneEffect,
    LoadParentChildEffect,
    LoadTransferPaneEffect,
    RunDirectorySizeEffect,
    RunFileSearchEffect,
    RunGoPathCompletionEffect,
    RunGrepSearchEffect,
    RunTextReplaceApplyEffect,
    RunTextReplacePreviewEffect,
)

CHILD_PANE_DEBOUNCE_SECONDS = 0.03
DOCUMENT_PREVIEW_DEBOUNCE_SECONDS = 0.35
FILE_SEARCH_DEBOUNCE_SECONDS = 0.2
GREP_SEARCH_DEBOUNCE_SECONDS = 0.2
GO_COMPLETION_DEBOUNCE_SECONDS = 0.06
DOCUMENT_PREVIEW_EXTENSIONS = frozenset({".pdf", ".docx", ".xlsx", ".pptx"})


@dataclass(frozen=True)
class SearchWorkerResult:
    """Terminal search payload including whether the result list was capped."""

    results: tuple[Any, ...]
    truncated: bool = False

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

GO_COMPLETION_TRACKING = TrackingConfig(
    effect_type=RunGoPathCompletionEffect,
    cancel_event_attr="_active_go_completion_cancel_event",
    request_id_attr="_active_go_completion_request_id",
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
        if hasattr(app, "_go_completion_service"):
            app._go_completion_service.invalidate(effect.invalidate_paths)
    run_worker(
        app,
        effect,
        partial(
            app._snapshot_loader.load_browser_snapshot,
            effect.path,
            effect.cursor_path,
            show_hidden=app._app_state.show_hidden,
            enable_image_preview=effect.enable_image_preview,
            enable_pdf_preview=effect.enable_pdf_preview,
            enable_office_preview=effect.enable_office_preview,
        ),
        WorkerSpec(
            name=f"browser-snapshot:{effect.request_id}",
            group="browser-snapshot",
            description=effect.path,
            exclusive=True,
        ),
    )


def schedule_child_pane_snapshot(app: Any, effect: LoadChildPaneSnapshotEffect) -> None:
    pending_effect = getattr(app, "_pending_child_pane_effect", None)
    if getattr(app, "_child_pane_timer", None) is not None and pending_effect is not None:
        start_child_pane_snapshot(app, pending_effect, require_pending_match=False)
    cancel_timer(app, "_child_pane_timer")
    debounce_seconds = _child_pane_debounce_seconds(effect)
    timer = app.set_timer(
        debounce_seconds,
        partial(start_child_pane_snapshot, app, effect),
        name=f"child-pane-snapshot-debounce:{effect.request_id}",
    )
    setattr(app, "_pending_child_pane_effect", effect)
    setattr(app, "_child_pane_timer", timer)


def start_child_pane_snapshot(
    app: Any,
    effect: LoadChildPaneSnapshotEffect,
    *,
    require_pending_match: bool = True,
) -> None:
    setattr(app, "_child_pane_timer", None)
    pending_effect = getattr(app, "_pending_child_pane_effect", None)
    if pending_effect == effect:
        setattr(app, "_pending_child_pane_effect", None)
    if require_pending_match and app._app_state.pending_child_pane_request_id != effect.request_id:
        return
    cancel_event = threading.Event()
    set_active_tracking(app, CHILD_PANE_TRACKING, effect.request_id, cancel_event)
    loader = partial(
        app._snapshot_loader.load_child_pane_snapshot,
        effect.current_path,
        effect.cursor_path,
        preview_max_bytes=effect.preview_max_bytes,
        enable_text_preview=effect.enable_text_preview,
        enable_image_preview=effect.enable_image_preview,
        image_preview_mode=effect.image_preview_mode,
        enable_pdf_preview=effect.enable_pdf_preview,
        enable_office_preview=effect.enable_office_preview,
        preview_columns=_child_preview_columns(app),
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
            show_hidden=app._app_state.show_hidden,
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
            enable_text_preview=effect.enable_text_preview,
            enable_image_preview=effect.enable_image_preview,
            image_preview_mode=effect.image_preview_mode,
            enable_pdf_preview=effect.enable_pdf_preview,
            enable_office_preview=effect.enable_office_preview,
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


def schedule_go_path_completion(app: Any, effect: RunGoPathCompletionEffect) -> None:
    """Debounce and run direct Go completion off the UI thread."""

    cancel_timer(app, "_go_completion_timer")
    timer = app.set_timer(
        GO_COMPLETION_DEBOUNCE_SECONDS,
        partial(start_go_path_completion_worker, app, effect),
        name=f"go-completion-debounce:{effect.request_id}",
    )
    app._go_completion_timer = timer


def start_go_path_completion_worker(app: Any, effect: RunGoPathCompletionEffect) -> None:
    app._go_completion_timer = None
    if app._app_state.pending_go_completion_request_id != effect.request_id:
        return
    cancel_event = threading.Event()
    set_active_tracking(app, GO_COMPLETION_TRACKING, effect.request_id, cancel_event)

    def run_completion() -> GoPathCompletionResult:
        return app._go_completion_service.complete(
            effect.query,
            effect.base_path,
            is_cancelled=cancel_event.is_set,
        )

    run_worker(
        app,
        effect,
        run_completion,
        WorkerSpec(
            name=f"go-completion:{effect.request_id}",
            group="go-completion",
            description=effect.query,
            exclusive=True,
        ),
    )


def cancel_pending_go_completion(app: Any) -> None:
    if hasattr(app, "_go_completion_timer"):
        cancel_timer(app, "_go_completion_timer")
    if hasattr(app, "_active_go_completion_cancel_event"):
        cancel_active_tracking(app, GO_COMPLETION_TRACKING)


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


def _child_pane_debounce_seconds(effect: LoadChildPaneSnapshotEffect) -> float:
    if (
        (effect.enable_pdf_preview or effect.enable_office_preview)
        and effect.grep_result is None
        and _is_document_preview_path(effect.cursor_path)
    ):
        return DOCUMENT_PREVIEW_DEBOUNCE_SECONDS
    return CHILD_PANE_DEBOUNCE_SECONDS


def _child_preview_columns(app: Any) -> int:
    try:
        from zivo.ui import ChildPane

        child_pane = app.query_one("#child-pane", ChildPane)
    except (NoMatches, Exception):
        try:
            import shutil

            cols = shutil.get_terminal_size().columns
            return max(1, cols // 3)
        except Exception:
            return 40
    width = child_pane.preview_render_width()
    if width > 0:
        return width
    try:
        import shutil

        cols = shutil.get_terminal_size().columns
        return max(1, cols // 3)
    except Exception:
        return 40


def _is_document_preview_path(path: str | None) -> bool:
    if path is None:
        return False
    return Path(path).suffix.casefold() in DOCUMENT_PREVIEW_EXTENSIONS


def schedule_text_replace_apply(app: Any, effect: RunTextReplaceApplyEffect) -> None:
    cancel_event = start_foreground_operation(app, effect.request_id)
    run_worker(
        app,
        effect,
        partial(
            app._text_replace_service.apply,
            effect.request,
            progress_callback=partial(
                report_foreground_operation_progress,
                app,
                effect.request_id,
            ),
            cancel_callback=cancel_event.is_set,
        ),
        WorkerSpec(
            name=f"text-replace-apply:{effect.request_id}",
            group="text-replace-apply",
            description="apply replacement",
            exclusive=True,
        ),
    )


def describe_search_effect(effect: RunFileSearchEffect | RunGrepSearchEffect) -> str:
    if isinstance(effect, RunFileSearchEffect):
        parts = [effect.query]
        if effect.include_extensions:
            parts.append(f"include={','.join(effect.include_extensions)}")
        if effect.exclude_extensions:
            parts.append(f"exclude={','.join(effect.exclude_extensions)}")
        return " | ".join(part for part in parts if part)
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

    palette = getattr(app._app_state, "command_palette", None)
    direct_file_search = (
        isinstance(effect, RunFileSearchEffect)
        and palette is not None
        and palette.source == "file_search"
    )
    direct_grep_search = (
        isinstance(effect, RunGrepSearchEffect)
        and palette is not None
        and palette.source == "grep_search"
    )

    if isinstance(effect, RunFileSearchEffect):
        search_kwargs["search_target"] = effect.search_target
        if effect.include_extensions or effect.exclude_extensions:
            search_kwargs["include_extensions"] = effect.include_extensions
            search_kwargs["exclude_extensions"] = effect.exclude_extensions

    if direct_file_search:
        configured_limit = app._app_state.config.file_search.max_results
        search_kwargs["max_results"] = (
            DEFAULT_SEARCH_MAX_RESULTS if configured_limit is None else configured_limit
        )
        search_kwargs["on_results"] = partial(
            report_search_results,
            app,
            effect.request_id,
            effect.query,
            "file_search",
        )
    if isinstance(effect, RunGrepSearchEffect):
        search_kwargs["include_globs"] = effect.include_globs
        search_kwargs["exclude_globs"] = effect.exclude_globs
        search_kwargs["target_paths"] = effect.target_paths
        search_kwargs["filename_filter"] = effect.filename_filter
        if direct_grep_search:
            configured_limit = app._app_state.config.grep_search.max_results
            search_kwargs["max_results"] = (
                DEFAULT_SEARCH_MAX_RESULTS if configured_limit is None else configured_limit
            )
            search_kwargs["on_results"] = partial(
                report_search_results,
                app,
                effect.request_id,
                effect.query,
                "grep_search",
            )
    truncated = False
    progress_callback = search_kwargs.get("on_results")

    def on_results(results: tuple[Any, ...], batch_truncated: bool) -> None:
        nonlocal truncated
        truncated = truncated or batch_truncated
        if progress_callback is not None:
            progress_callback(results, batch_truncated)

    if "on_results" in search_kwargs:
        search_kwargs["on_results"] = on_results

    def run_search() -> SearchWorkerResult | tuple[Any, ...]:
        used_progress_callback = True
        try:
            result = service.search(
                effect.root_path,
                effect.query,
                **search_kwargs,
            )
        except TypeError as error:
            # Keep older/custom service implementations working while the
            # optional progress callback is adopted.
            if "on_results" not in search_kwargs or "on_results" not in str(error):
                raise
            used_progress_callback = False
            fallback_kwargs = dict(search_kwargs)
            fallback_kwargs.pop("on_results")
            result = service.search(
                effect.root_path,
                effect.query,
                **fallback_kwargs,
            )
        if not direct_file_search and not direct_grep_search:
            return result
        result_tuple = tuple(result)
        if not used_progress_callback:
            limit = search_kwargs.get("max_results")
            if isinstance(limit, int) and limit >= 0 and len(result_tuple) > limit:
                result_tuple = result_tuple[:limit]
                on_results(result_tuple, True)
        return SearchWorkerResult(result_tuple, truncated)

    run_worker(
        app,
        effect,
        run_search,
        WorkerSpec(
            name=f"{config.worker_key}:{effect.request_id}",
            group=config.worker_key,
            description=describe_search_effect(effect),
            exclusive=True,
        ),
    )
