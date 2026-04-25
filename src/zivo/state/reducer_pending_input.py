"""Pending input validation and request builders."""

from pathlib import Path

from zivo.archive_utils import resolve_zip_destination_input
from zivo.models import (
    CreatePathRequest,
    CreateZipArchiveRequest,
    ExtractArchiveRequest,
    RenameRequest,
)

from .reducer_path_helpers import current_entry_paths


def validate_pending_input(state, *, is_macos: bool) -> str | None:
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

    if state.pending_input.zip_source_paths is not None:
        destination = state.pending_input.value.strip()
        if not destination:
            return "Destination path cannot be empty"
        resolved_destination = Path(
            resolve_zip_destination_input(state.current_pane.directory_path, destination)
        )
        if resolved_destination.suffix.casefold() != ".zip":
            return "Destination path must end with .zip"
        if resolved_destination.exists() and resolved_destination.is_dir():
            return "Destination path already exists as a directory"

        for source_path_str in state.pending_input.zip_source_paths:
            source_path = Path(source_path_str).expanduser().resolve()
            if resolved_destination == source_path:
                return "Destination path cannot be one of the source paths"
            if source_path.is_dir() and not source_path.is_symlink():
                if resolved_destination.is_relative_to(source_path):
                    return "Destination path cannot be inside a directory being compressed"
        return None

    name = state.pending_input.value
    if not name:
        return "Name cannot be empty"
    if name in {".", ".."}:
        return "'.' and '..' are not valid names"
    if "/" in name or "\\" in name:
        return "Names cannot include path separators"
    if is_macos and ":" in name:
        return "Names cannot include colons"

    parent_path, current_target_path = pending_input_parent_and_target(state)
    if parent_path is None:
        return "Unable to resolve target directory"

    existing_paths = _pending_input_existing_paths(state)
    if is_macos:
        name_cf = name.casefold()
        for existing_path in existing_paths:
            existing_name_cf = Path(existing_path).name.casefold()
            if existing_name_cf == name_cf and existing_path != current_target_path:
                return f"An entry named '{name}' already exists"
    else:
        candidate_path = str(Path(parent_path) / name)
        if candidate_path in existing_paths and candidate_path != current_target_path:
            return f"An entry named '{name}' already exists"
    return None


def is_name_conflict_validation_error(state, message: str) -> bool:
    return state.pending_input is not None and message == (
        f"An entry named '{state.pending_input.value}' already exists"
    )


def name_conflict_kind(state):
    if state.pending_input is not None and state.pending_input.create_kind == "file":
        return "create_file"
    if state.pending_input is not None and state.pending_input.create_kind == "dir":
        return "create_dir"
    return "rename"


def build_file_mutation_request(
    state,
) -> RenameRequest | CreatePathRequest | None:
    if state.pending_input is None:
        return None
    if state.ui_mode == "RENAME" and state.pending_input.target_path is not None:
        return RenameRequest(
            source_path=state.pending_input.target_path,
            new_name=state.pending_input.value,
        )
    if state.ui_mode == "CREATE" and state.pending_input.create_kind is not None:
        # Use the active transfer pane's directory path in transfer mode
        if state.layout_mode == "transfer":
            active_pane = (
                state.transfer_left
                if state.active_transfer_pane == "left"
                else state.transfer_right
            )
            parent_dir = (
                active_pane.current_path
                if active_pane
                else state.current_pane.directory_path
            )
        else:
            parent_dir = state.current_pane.directory_path
        return CreatePathRequest(
            parent_dir=parent_dir,
            name=state.pending_input.value,
            kind=state.pending_input.create_kind,
        )
    return None


def build_extract_archive_request(state) -> ExtractArchiveRequest | None:
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


def build_zip_compress_request(state) -> CreateZipArchiveRequest | None:
    if state.pending_input is None or state.pending_input.zip_source_paths is None:
        return None

    destination = state.pending_input.value.strip()
    if not destination:
        return None

    return CreateZipArchiveRequest(
        source_paths=state.pending_input.zip_source_paths,
        destination_path=resolve_zip_destination_input(
            state.current_pane.directory_path,
            destination,
        ),
        root_dir=state.current_pane.directory_path,
    )


def pending_input_parent_and_target(state) -> tuple[str | None, str | None]:
    if state.pending_input is None:
        return (None, None)
    if state.ui_mode == "RENAME" and state.pending_input.target_path is not None:
        target_path = Path(state.pending_input.target_path)
        return (str(target_path.parent), str(target_path))
    if state.ui_mode == "CREATE":
        if state.layout_mode == "transfer":
            active_pane = _active_transfer_pane(state)
            if active_pane is not None:
                return (active_pane.current_path, None)
        return (state.current_pane.directory_path, None)
    if state.ui_mode == "EXTRACT" and state.pending_input.extract_source_path is not None:
        source_path = Path(state.pending_input.extract_source_path)
        return (str(source_path.parent), None)
    if state.ui_mode == "ZIP" and state.pending_input.zip_source_paths is not None:
        return (state.current_pane.directory_path, None)
    return (None, None)


def _active_transfer_pane(state):
    if state.layout_mode != "transfer":
        return None
    if state.active_transfer_pane == "left":
        return state.transfer_left
    return state.transfer_right


def _pending_input_existing_paths(state) -> tuple[str, ...]:
    if state.layout_mode == "transfer":
        active_pane = _active_transfer_pane(state)
        if active_pane is not None:
            return tuple(entry.path for entry in active_pane.pane.entries)
    return current_entry_paths(state)
