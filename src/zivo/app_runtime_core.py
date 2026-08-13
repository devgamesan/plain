"""Shared runtime helpers for effect scheduling and worker tracking."""

import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from textual.timer import Timer

from zivo.state import Effect


@dataclass(frozen=True)
class WorkerSpec:
    name: str
    group: str
    description: str
    exclusive: bool | None = None


@dataclass(frozen=True)
class TrackingConfig:
    effect_type: type[Any]
    cancel_event_attr: str
    request_id_attr: str


@dataclass(frozen=True)
class SearchRuntimeConfig:
    debounce_seconds: float
    worker_key: str
    timer_attr: str
    pending_request_attr: str
    service_attr: str
    tracking: TrackingConfig


def start_foreground_operation(app: Any, operation_id: int) -> threading.Event:
    """Create the cooperative cancel event for the active foreground operation."""

    event = threading.Event()
    app._foreground_operation_cancel_event = event
    app._foreground_operation_id = operation_id
    return event


def request_foreground_operation_cancel(app: Any, operation_id: int) -> None:
    """Set the cancel flag when it still belongs to the requested operation."""

    if getattr(app, "_foreground_operation_id", None) != operation_id:
        return
    event = getattr(app, "_foreground_operation_cancel_event", None)
    if event is not None:
        event.set()


def clear_foreground_operation(app: Any, operation_id: int) -> None:
    """Release foreground operation tracking after a terminal result."""

    if getattr(app, "_foreground_operation_id", None) != operation_id:
        return
    app._foreground_operation_cancel_event = None
    app._foreground_operation_id = None


def start_background_command(app: Any, request_id: int) -> threading.Event:
    """Create the cancel event for a non-interactive external command."""

    event = threading.Event()
    app._background_command_cancel_event = event
    app._background_command_request_id = request_id
    return event


def request_background_command_cancel(app: Any, request_id: int) -> None:
    """Signal the matching external command to terminate."""

    if getattr(app, "_background_command_request_id", None) != request_id:
        return
    event = getattr(app, "_background_command_cancel_event", None)
    if event is not None:
        event.set()


def clear_background_command(app: Any, request_id: int) -> None:
    """Release cancellation tracking for a completed external command."""

    if getattr(app, "_background_command_request_id", None) != request_id:
        return
    app._background_command_cancel_event = None
    app._background_command_request_id = None


CompleteActionHandler = Callable[[Effect, object], tuple[Any, ...]]
FailureActionHandler = Callable[[Effect, BaseException | None, str], tuple[Any, ...]]


def run_worker(
    app: Any,
    effect: Effect,
    worker_fn: Callable[[], object],
    spec: WorkerSpec,
) -> None:
    worker_kwargs = {
        "name": spec.name,
        "group": spec.group,
        "description": spec.description,
        "exit_on_error": False,
        "thread": True,
    }
    if spec.exclusive is not None:
        worker_kwargs["exclusive"] = spec.exclusive
    worker = app.run_worker(worker_fn, **worker_kwargs)
    app._pending_workers[worker.name] = effect


def cancel_timer(app: Any, timer_attr: str) -> None:
    timer = getattr(app, timer_attr)
    if timer is None:
        return
    cast_timer: Timer = timer
    cast_timer.stop()
    setattr(app, timer_attr, None)


def set_active_tracking(
    app: Any,
    tracking: TrackingConfig,
    request_id: int,
    cancel_event: threading.Event,
) -> None:
    setattr(app, tracking.cancel_event_attr, cancel_event)
    setattr(app, tracking.request_id_attr, request_id)


def cancel_active_tracking(app: Any, tracking: TrackingConfig) -> None:
    cancel_event = getattr(app, tracking.cancel_event_attr, None)
    if cancel_event is None:
        return
    cancel_event.set()
    setattr(app, tracking.cancel_event_attr, None)
    setattr(app, tracking.request_id_attr, None)


def clear_tracking_for_request(app: Any, tracking: TrackingConfig, request_id: int) -> None:
    if getattr(app, tracking.request_id_attr) != request_id:
        return
    setattr(app, tracking.cancel_event_attr, None)
    setattr(app, tracking.request_id_attr, None)


def find_handler(
    value: object,
    handlers: tuple[tuple[type[Any], Callable[..., tuple[Any, ...]]], ...],
) -> Callable[..., tuple[Any, ...]] | None:
    for value_type, handler in handlers:
        if isinstance(value, value_type):
            return handler
    return None
