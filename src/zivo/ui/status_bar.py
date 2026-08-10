"""Status bar widget for the initial shell layout."""

from rich.cells import cell_len
from rich.style import Style
from rich.text import Text
from textual.events import Click
from textual.message import Message
from textual.timer import Timer
from textual.widgets import Static

from zivo.models.shell_data import StatusBarState


class StatusBar(Static):
    """Compact notification line shown at the bottom of the screen."""

    def __init__(
        self,
        state: StatusBarState,
        *,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(self._render_state(state), id=id, classes=classes)
        self.state = state
        self._auto_dismiss_timer: Timer | None = None

    class ActionClicked(Message):
        """Notify the app that the displayed notification action was clicked."""

        def __init__(self, action_id: str, revision: int) -> None:
            super().__init__()
            self.action_id = action_id
            self.revision = revision

    class AutoDismiss(Message):
        """Request revision-checked dismissal after the display timer expires."""

        def __init__(self, revision: int) -> None:
            super().__init__()
            self.revision = revision

    @staticmethod
    def format_state(state: StatusBarState) -> str:
        """Build the visible notification line."""

        if not state.message:
            return ""
        label = state.message_level or "message"
        return f"{label}: {state.message}"

    def on_mount(self) -> None:
        self._refresh_renderable()

    def on_resize(self, event) -> None:
        del event
        self._refresh_renderable()

    def _refresh_renderable(self) -> None:
        width = self.content_region.width or self.size.width
        self.update(self._render_state(self.state, width=width or None))

    def set_state(self, state: StatusBarState) -> None:
        """Update the rendered line without remounting the widget."""

        if state == self.state:
            return

        if self._auto_dismiss_timer is not None:
            self._auto_dismiss_timer.stop()
            self._auto_dismiss_timer = None
        self.state = state
        self._refresh_renderable()
        if state.auto_dismiss and state.message:
            self._auto_dismiss_timer = self.set_timer(
                5.0,
                lambda: self.post_message(self.AutoDismiss(state.notification_revision)),
            )

    @classmethod
    def _render_state(cls, state: StatusBarState, *, width: int | None = None) -> Text:
        message = Text(cls.format_state(state), no_wrap=True, overflow="ellipsis")
        if state.action is None:
            return message

        action_gap = "   "
        action_width = cell_len(action_gap) + cell_len(state.action.label)
        action_label = state.action.label
        if width is not None and width <= action_width:
            available_action_width = max(1, width)
            message = Text()
            action_gap = ""
            action_label = cls._fit_action_label(
                state.action.label,
                available_action_width,
            )
        elif width is not None and width > 0:
            message.truncate(max(0, width - action_width), overflow="ellipsis")
        rendered = message.copy()
        rendered.no_wrap = True
        rendered.overflow = "crop"
        rendered.append(action_gap)
        rendered.append(
            action_label,
            style=Style(
                bold=True,
                underline=True,
                meta={
                    "notification_action_id": state.action.action_id,
                    "notification_revision": state.notification_revision,
                },
            )
        )
        return rendered

    @staticmethod
    def _fit_action_label(label: str, width: int) -> str:
        """Keep a shortened action label inside an extremely narrow status bar."""

        if cell_len(label) <= width:
            return label
        shortened = Text(label, no_wrap=True, overflow="ellipsis")
        shortened.truncate(width, overflow="ellipsis")
        return shortened.plain

    async def on_click(self, event: Click) -> None:
        """Forward only the clickable action span to the app dispatcher."""

        meta = event.style.meta or {}
        action_id = meta.get("notification_action_id")
        revision = meta.get("notification_revision")
        if not isinstance(action_id, str) or not isinstance(revision, int):
            return
        event.stop()
        handler = getattr(self.app, "on_status_bar_action_clicked", None)
        if handler is not None:
            await handler(self.ActionClicked(action_id, revision))
