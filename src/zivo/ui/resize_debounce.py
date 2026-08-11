"""Helpers for coalescing expensive widget work during terminal resizes."""

from collections.abc import Callable

from textual.timer import Timer
from textual.widget import Widget

RESIZE_DEBOUNCE_SECONDS = 0.05


class ResizeDebouncer:
    """Run a resize callback once after a burst of resize events."""

    def __init__(self, owner: Widget, callback: Callable[[], None], *, name: str) -> None:
        self._owner = owner
        self._callback = callback
        self._name = name
        self._timer: Timer | None = None
        self._generation = 0

    def schedule(self) -> None:
        """Reset the debounce window and schedule the latest resize callback."""

        self._generation += 1
        generation = self._generation
        if self._timer is not None:
            self._timer.stop()
        self._timer = self._owner.set_timer(
            RESIZE_DEBOUNCE_SECONDS,
            lambda: self._run(generation),
            name=self._name,
        )

    def stop(self) -> None:
        """Cancel pending work, including callbacks from stale timers."""

        self._generation += 1
        if self._timer is not None:
            self._timer.stop()
            self._timer = None

    def _run(self, generation: int) -> None:
        if generation != self._generation:
            return
        self._timer = None
        self._callback()
