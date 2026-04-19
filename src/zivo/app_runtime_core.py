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
    cancel_event = getattr(app, tracking.cancel_event_attr)
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
