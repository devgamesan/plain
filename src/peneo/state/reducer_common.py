"""Shared helpers for reducer action handlers."""

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from peneo.models import (
    AppConfig,
    CreatePathRequest,
    ExternalLaunchRequest,
    ExtractArchiveRequest,
    FileMutationResult,
    PasteRequest,
    PasteSummary,
    RenameRequest,
    TrashDeleteRequest,
)

from .actions import Action, RequestDirectorySizes
from .effects import (
    Effect,
    LoadBrowserSnapshotEffect,
    LoadChildPaneSnapshotEffect,
    ReduceResult,
    RunArchiveExtractEffect,
    RunArchivePreparationEffect,
    RunClipboardPasteEffect,
    RunExternalLaunchEffect,
    RunFileMutationEffect,
)
from .models import (
    AppState,
    DirectoryEntryState,
    DirectorySizeCacheEntry,
    FileSearchResultState,
    HistoryState,
    NameConflictKind,
    NotificationState,
    PaneState,
    SortState,
)
from .selectors import select_target_paths, select_visible_current_entry_states

ReducerFn = Callable[[AppState, Action], ReduceResult]

CONFIG_SORT_FIELDS = ("name", "modified", "size")
CONFIG_THEMES = ("textual-dark", "textual-light")
CONFIG_PASTE_ACTIONS = ("prompt", "overwrite", "skip", "rename")
CONFIG_EDITOR_COMMANDS = (None, "nvim", "vim", "nano", "hx", "micro", "emacs -nw")
REGEX_FILE_SEARCH_PREFIX = "re:"
REGEX_GREP_SEARCH_PREFIX = "re:"


def done(next_state: AppState, *effects: Effect) -> ReduceResult:
    return ReduceResult(state=next_state, effects=effects)


def current_entry_paths(state: AppState) -> set[str]:
    return {entry.path for entry in active_current_entries(state)}


def active_current_entries(state: AppState) -> tuple[DirectoryEntryState, ...]:
    return state.current_pane.entries


def expand_and_validate_path(query: str, base_path: str) -> str | None:
    """Expand ~, ., .. and validate path exists and is a directory."""
    _ = base_path
    if not query or not query.strip():
        return None
    try:
        expanded = Path(query).expanduser().resolve()
        if not expanded.exists():
            return None
        if not expanded.is_dir():
            return None
        return str(expanded)
    except (OSError, ValueError, RuntimeError):
        return None


def normalize_selected_paths(
    selected_paths: frozenset[str],
    entries: tuple[DirectoryEntryState, ...],
) -> frozenset[str]:
    entry_paths = {entry.path for entry in entries}
    return frozenset(path for path in selected_paths if path in entry_paths)


def move_cursor(
    current_path: str | None,
    visible_paths: tuple[str, ...],
    delta: int,
) -> str | None:
    if not visible_paths:
        return None

    if current_path in visible_paths:
        current_index = visible_paths.index(current_path)
    else:
        current_index = 0

    next_index = max(0, min(len(visible_paths) - 1, current_index + delta))
    return visible_paths[next_index]


def run_paste_request(state: AppState, request: PasteRequest) -> ReduceResult:
    request_id = state.next_request_id
    next_state = replace(
        state,
        notification=None,
        paste_conflict=None,
        delete_confirmation=None,
        pending_paste_request_id=request_id,
        next_request_id=request_id + 1,
        ui_mode="BUSY",
    )
    return ReduceResult(
        state=next_state,
        effects=(RunClipboardPasteEffect(request_id=request_id, request=request),),
    )


def run_external_launch_request(
    state: AppState,
    request: ExternalLaunchRequest,
) -> ReduceResult:
    request_id = state.next_request_id
    next_state = replace(
        state,
        next_request_id=request_id + 1,
    )
    return ReduceResult(
        state=next_state,
        effects=(RunExternalLaunchEffect(request_id=request_id, request=request),),
    )


def run_file_mutation_request(
    state: AppState,
    request: RenameRequest | CreatePathRequest | TrashDeleteRequest,
) -> ReduceResult:
    request_id = state.next_request_id
    next_state = replace(
        state,
        notification=None,
        delete_confirmation=None,
        pending_file_mutation_request_id=request_id,
        next_request_id=request_id + 1,
        ui_mode="BUSY",
    )
    return ReduceResult(
        state=next_state,
        effects=(RunFileMutationEffect(request_id=request_id, request=request),),
    )


def run_archive_prepare_request(
    state: AppState,
    request: ExtractArchiveRequest,
) -> ReduceResult:
    request_id = state.next_request_id
    next_state = replace(
        state,
        notification=NotificationState(level="info", message="Preparing archive extraction"),
        delete_confirmation=None,
        archive_extract_confirmation=None,
        archive_extract_progress=None,
        pending_archive_prepare_request_id=request_id,
        next_request_id=request_id + 1,
        ui_mode="BUSY",
    )
    return ReduceResult(
        state=next_state,
        effects=(RunArchivePreparationEffect(request_id=request_id, request=request),),
    )


def run_archive_extract_request(
    state: AppState,
    request: ExtractArchiveRequest,
) -> ReduceResult:
    request_id = state.next_request_id
    next_state = replace(
        state,
        notification=NotificationState(level="info", message="Extracting archive..."),
        archive_extract_confirmation=None,
        archive_extract_progress=None,
        pending_archive_extract_request_id=request_id,
        next_request_id=request_id + 1,
        ui_mode="BUSY",
    )
    return ReduceResult(
        state=next_state,
        effects=(RunArchiveExtractEffect(request_id=request_id, request=request),),
    )


def cursor_path_after_file_mutation(
    state: AppState,
    result: FileMutationResult,
) -> str | None:
    active_entries = active_current_entries(state)
    if result.removed_paths:
        remaining_paths = [
            entry.path
            for entry in active_entries
            if entry.path not in result.removed_paths
        ]
        if not remaining_paths:
            return None
        current_cursor = state.current_pane.cursor_path
        if current_cursor is not None and current_cursor not in result.removed_paths:
            return current_cursor
        original_paths = [entry.path for entry in active_entries]
        if current_cursor in original_paths:
            current_index = original_paths.index(current_cursor)
            if current_index < len(remaining_paths):
                return remaining_paths[current_index]
        return remaining_paths[-1]
    return result.path


def restore_ui_mode_after_pending_input(state: AppState) -> str:
    if state.pending_input is None:
        return "BROWSING"
    if state.pending_input.extract_source_path is not None:
        return "EXTRACT"
    if state.pending_input.create_kind is not None:
        return "CREATE"
    return "RENAME"


def request_snapshot_refresh(
    state: AppState,
    *,
    cursor_path: str | None = None,
    keep_current_cursor: bool = True,
) -> ReduceResult:
    request_id = state.next_request_id
    next_state = replace(
        state,
        pending_browser_snapshot_request_id=request_id,
        pending_child_pane_request_id=None,
        next_request_id=request_id + 1,
    )
    return ReduceResult(
        state=next_state,
        effects=(
            LoadBrowserSnapshotEffect(
                request_id=request_id,
                path=state.current_path,
                cursor_path=(
                    state.current_pane.cursor_path
                    if keep_current_cursor and cursor_path is None
                    else cursor_path
                ),
                blocking=False,
            ),
        ),
    )


def maybe_request_directory_sizes(
    state: AppState,
    reduce_state: ReducerFn,
    *effects: Effect,
) -> ReduceResult:
    target_paths = directory_size_target_paths(state)
    if not target_paths:
        return ReduceResult(state=state, effects=effects)

    cache_by_path = directory_size_cache_by_path(state.directory_size_cache)
    pending_paths = tuple(
        path
        for path in target_paths
        if cache_by_path.get(path) is not None and cache_by_path[path].status == "pending"
    )
    missing_paths = tuple(path for path in target_paths if cache_by_path.get(path) is None)

    if not missing_paths:
        if pending_paths and state.pending_directory_size_request_id is None:
            return reduce_state(state, RequestDirectorySizes(pending_paths))
        return ReduceResult(state=state, effects=effects)

    request_paths = tuple(dict.fromkeys((*pending_paths, *missing_paths)))
    result = reduce_state(state, RequestDirectorySizes(request_paths))
    return ReduceResult(state=result.state, effects=(*effects, *result.effects))


def directory_size_target_paths(state: AppState) -> tuple[str, ...]:
    display_directory_sizes = state.config.display.show_directory_sizes
    target_paths: list[str] = []
    if display_directory_sizes:
        target_paths.extend(visible_directory_paths(state.parent_pane.entries, state.show_hidden))
    target_paths.extend(
        visible_directory_paths(select_visible_current_entry_states(state), show_hidden=True)
    )
    if display_directory_sizes:
        target_paths.extend(visible_directory_paths(state.child_pane.entries, state.show_hidden))
    if not display_directory_sizes and state.sort.field != "size":
        return ()
    if display_directory_sizes:
        return tuple(dict.fromkeys(target_paths))
    return tuple(
        dict.fromkeys(
            visible_directory_paths(select_visible_current_entry_states(state), show_hidden=True)
        )
    )


def visible_directory_paths(
    entries: tuple[DirectoryEntryState, ...],
    show_hidden: bool,
) -> tuple[str, ...]:
    return tuple(
        entry.path
        for entry in entries
        if entry.kind == "dir" and (show_hidden or not entry.hidden)
    )


def directory_size_cache_by_path(
    entries: tuple[DirectorySizeCacheEntry, ...],
) -> dict[str, DirectorySizeCacheEntry]:
    return {entry.path: entry for entry in entries}


def upsert_directory_size_entries(
    current_entries: tuple[DirectorySizeCacheEntry, ...],
    new_entries: tuple[DirectorySizeCacheEntry, ...],
) -> tuple[DirectorySizeCacheEntry, ...]:
    cache_by_path = directory_size_cache_by_path(current_entries)
    for entry in new_entries:
        cache_by_path[entry.path] = entry
    return tuple(sorted(cache_by_path.values(), key=lambda entry: entry.path))


def sync_child_pane(
    state: AppState,
    cursor_path: str | None,
    reduce_state: ReducerFn,
) -> ReduceResult:
    entry = current_entry_for_path(state, cursor_path)
    if entry is None or entry.kind != "dir":
        next_state = replace(
            state,
            child_pane=PaneState(directory_path=state.current_path, entries=()),
            pending_child_pane_request_id=None,
        )
        return maybe_request_directory_sizes(next_state, reduce_state)

    if (
        entry.path == state.child_pane.directory_path
        and state.pending_child_pane_request_id is None
    ):
        return maybe_request_directory_sizes(state, reduce_state)

    request_id = state.next_request_id
    next_state = replace(
        state,
        pending_child_pane_request_id=request_id,
        next_request_id=request_id + 1,
    )
    return maybe_request_directory_sizes(
        next_state,
        reduce_state,
        LoadChildPaneSnapshotEffect(
            request_id=request_id,
            current_path=state.current_path,
            cursor_path=entry.path,
        ),
    )


def current_entry_for_path(
    state: AppState,
    path: str | None,
) -> DirectoryEntryState | None:
    if path is None:
        return None
    for entry in active_current_entries(state):
        if entry.path == path:
            return entry
    return None


def single_target_entry(state: AppState) -> DirectoryEntryState | None:
    target_paths = select_target_paths(state)
    if len(target_paths) != 1:
        return None
    return current_entry_for_path(state, target_paths[0])


def single_target_path(state: AppState) -> str | None:
    entry = single_target_entry(state)
    return entry.path if entry else None


def normalize_cursor_path(
    entries: tuple[DirectoryEntryState, ...],
    current_cursor: str | None,
) -> str | None:
    entry_paths = {entry.path for entry in entries}
    if current_cursor in entry_paths:
        return current_cursor
    if not entries:
        return None
    return entries[0].path


def normalize_config_editor_cursor(cursor_index: int) -> int:
    return max(0, min(len(config_editor_labels()) - 1, cursor_index))


def cycle_config_editor_value(config: AppConfig, cursor_index: int, delta: int) -> AppConfig:
    field_id = config_editor_field_ids()[normalize_config_editor_cursor(cursor_index)]
    if field_id == "editor.command":
        return replace(
            config,
            editor=replace(
                config.editor,
                command=cycle_editor_command(config.editor.command, delta),
            ),
        )
    if field_id == "display.show_hidden_files":
        return replace(
            config,
            display=replace(
                config.display,
                show_hidden_files=not config.display.show_hidden_files,
            ),
        )
    if field_id == "display.show_directory_sizes":
        return replace(
            config,
            display=replace(
                config.display,
                show_directory_sizes=not config.display.show_directory_sizes,
            ),
        )
    if field_id == "display.theme":
        return replace(
            config,
            display=replace(
                config.display,
                theme=cycle_choice(
                    CONFIG_THEMES,
                    config.display.theme,
                    delta,
                ),
            ),
        )
    if field_id == "display.default_sort_field":
        return replace(
            config,
            display=replace(
                config.display,
                default_sort_field=cycle_choice(
                    CONFIG_SORT_FIELDS,
                    config.display.default_sort_field,
                    delta,
                ),
            ),
        )
    if field_id == "display.default_sort_descending":
        return replace(
            config,
            display=replace(
                config.display,
                default_sort_descending=not config.display.default_sort_descending,
            ),
        )
    if field_id == "display.directories_first":
        return replace(
            config,
            display=replace(
                config.display,
                directories_first=not config.display.directories_first,
            ),
        )
    if field_id == "behavior.confirm_delete":
        return replace(
            config,
            behavior=replace(
                config.behavior,
                confirm_delete=not config.behavior.confirm_delete,
            ),
        )
    return replace(
        config,
        behavior=replace(
            config.behavior,
            paste_conflict_action=cycle_choice(
                CONFIG_PASTE_ACTIONS,
                config.behavior.paste_conflict_action,
                delta,
            ),
        ),
    )


def cycle_choice(options: tuple[str, ...], current: str, delta: int) -> str:
    current_index = options.index(current) if current in options else 0
    return options[(current_index + delta) % len(options)]


def cycle_editor_command(current: str | None, delta: int) -> str | None:
    if current in CONFIG_EDITOR_COMMANDS:
        current_index = CONFIG_EDITOR_COMMANDS.index(current)
    else:
        current_index = len(CONFIG_EDITOR_COMMANDS)
    return CONFIG_EDITOR_COMMANDS[(current_index + delta) % len(CONFIG_EDITOR_COMMANDS)]


def config_editor_field_ids() -> tuple[str, ...]:
    return (
        "editor.command",
        "display.show_hidden_files",
        "display.theme",
        "display.show_directory_sizes",
        "display.default_sort_field",
        "display.default_sort_descending",
        "display.directories_first",
        "behavior.confirm_delete",
        "behavior.paste_conflict_action",
    )


def config_editor_labels() -> tuple[str, ...]:
    return (
        "Editor command",
        "Show hidden files",
        "Theme",
        "Show directory sizes",
        "Default sort field",
        "Default sort descending",
        "Directories first",
        "Confirm delete",
        "Paste conflict action",
    )


def apply_config_to_runtime_state(state: AppState, config: AppConfig) -> AppState:
    return replace(
        state,
        show_hidden=config.display.show_hidden_files,
        sort=SortState(
            field=config.display.default_sort_field,
            descending=config.display.default_sort_descending,
            directories_first=config.display.directories_first,
        ),
        confirm_delete=config.behavior.confirm_delete,
        paste_conflict_action=config.behavior.paste_conflict_action,
    )


def validate_pending_input(state: AppState) -> str | None:
    if state.pending_input is None:
        return "No input is active"

    if state.pending_input.extract_source_path is not None:
        destination = state.pending_input.value.strip()
        if not destination:
            return "Destination path cannot be empty"
        source_path = Path(state.pending_input.extract_source_path)
        resolved_destination = Path(destination).expanduser()
        if not resolved_destination.is_absolute():
            resolved_destination = source_path.parent / resolved_destination
        resolved_destination = resolved_destination.resolve(strict=False)
        if resolved_destination == source_path:
            return "Destination path cannot be the archive file itself"
        if resolved_destination.exists() and not resolved_destination.is_dir():
            return "Destination path must be a directory"
        return None

    name = state.pending_input.value
    if not name:
        return "Name cannot be empty"
    if name in {".", ".."}:
        return "'.' and '..' are not valid names"
    if "/" in name or "\\" in name:
        return "Names cannot include path separators"

    parent_path, current_target_path = pending_input_parent_and_target(state)
    if parent_path is None:
        return "Unable to resolve target directory"

    candidate_path = str(Path(parent_path) / name)
    existing_paths = current_entry_paths(state)
    if candidate_path in existing_paths and candidate_path != current_target_path:
        return f"An entry named '{name}' already exists"
    return None


def is_name_conflict_validation_error(state: AppState, message: str) -> bool:
    return state.pending_input is not None and message == (
        f"An entry named '{state.pending_input.value}' already exists"
    )


def name_conflict_kind(state: AppState) -> NameConflictKind:
    if state.pending_input is not None and state.pending_input.create_kind == "file":
        return "create_file"
    if state.pending_input is not None and state.pending_input.create_kind == "dir":
        return "create_dir"
    return "rename"


def build_file_mutation_request(
    state: AppState,
) -> RenameRequest | CreatePathRequest | None:
    if state.pending_input is None:
        return None
    if state.ui_mode == "RENAME" and state.pending_input.target_path is not None:
        return RenameRequest(
            source_path=state.pending_input.target_path,
            new_name=state.pending_input.value,
        )
    if state.ui_mode == "CREATE" and state.pending_input.create_kind is not None:
        return CreatePathRequest(
            parent_dir=state.current_pane.directory_path,
            name=state.pending_input.value,
            kind=state.pending_input.create_kind,
        )
    return None


def build_extract_archive_request(state: AppState) -> ExtractArchiveRequest | None:
    if state.pending_input is None or state.pending_input.extract_source_path is None:
        return None

    destination = state.pending_input.value.strip()
    if not destination:
        return None

    source_path = Path(state.pending_input.extract_source_path).expanduser().resolve()
    resolved_destination = Path(destination).expanduser()
    if not resolved_destination.is_absolute():
        resolved_destination = source_path.parent / resolved_destination

    return ExtractArchiveRequest(
        source_path=str(source_path),
        destination_path=str(resolved_destination.resolve(strict=False)),
    )


def pending_input_parent_and_target(state: AppState) -> tuple[str | None, str | None]:
    if state.pending_input is None:
        return (None, None)
    if state.ui_mode == "RENAME" and state.pending_input.target_path is not None:
        target_path = Path(state.pending_input.target_path)
        return (str(target_path.parent), str(target_path))
    if state.ui_mode == "CREATE":
        return (state.current_pane.directory_path, None)
    if state.ui_mode == "EXTRACT" and state.pending_input.extract_source_path is not None:
        source_path = Path(state.pending_input.extract_source_path)
        return (str(source_path.parent), None)
    return (None, None)


def filter_file_search_results(
    results: tuple[FileSearchResultState, ...],
    normalized_query: str,
) -> tuple[FileSearchResultState, ...]:
    return tuple(
        result
        for result in results
        if normalized_query in Path(result.path).name.casefold()
    )


def is_regex_file_search_query(query: str) -> bool:
    return query.strip().startswith(REGEX_FILE_SEARCH_PREFIX)


def format_clipboard_message(prefix: str, paths: tuple[str, ...]) -> str:
    noun = "item" if len(paths) == 1 else "items"
    return f"{prefix} {len(paths)} {noun} to clipboard"


def notification_for_external_launch(
    request: ExternalLaunchRequest,
) -> NotificationState | None:
    if request.kind != "copy_paths":
        return None
    noun = "path" if len(request.paths) == 1 else "paths"
    return NotificationState(
        level="info",
        message=f"Copied {len(request.paths)} {noun} to system clipboard",
    )


def split_terminal_exit_message(exit_code: int | None) -> str:
    if exit_code is None:
        return "Split terminal closed"
    return f"Split terminal closed (exit {exit_code})"


def notification_for_paste_summary(summary: PasteSummary) -> NotificationState:
    verb = "Copied" if summary.mode == "copy" else "Moved"
    if summary.failure_count and summary.success_count:
        return NotificationState(
            level="warning",
            message=(
                f"{verb} {summary.success_count}/{summary.total_count} items"
                f" with {summary.failure_count} failure(s)"
            ),
        )
    if summary.failure_count and not summary.success_count and not summary.skipped_count:
        return NotificationState(
            level="error",
            message=f"Failed to {summary.mode} {summary.total_count} item(s)",
        )
    if summary.skipped_count and not summary.success_count and not summary.failure_count:
        return NotificationState(
            level="info",
            message=f"Skipped {summary.skipped_count} conflicting item(s)",
        )
    message = f"{verb} {summary.success_count} item(s)"
    if summary.skipped_count:
        message += f", skipped {summary.skipped_count}"
    return NotificationState(level="info", message=message)


def build_history_after_snapshot_load(
    state: AppState,
    next_path: str,
) -> HistoryState:
    previous_path = state.current_path
    new_history = state.history
    if next_path != previous_path:
        history = state.history
        if history.forward and next_path == history.forward[0]:
            new_history = HistoryState(
                back=(*history.back, previous_path),
                forward=history.forward[1:],
            )
        elif history.back and next_path == history.back[-1]:
            new_history = HistoryState(
                back=history.back[:-1],
                forward=(previous_path, *history.forward),
            )
        else:
            new_history = HistoryState(
                back=(*history.back, previous_path),
                forward=(),
            )
    return new_history
