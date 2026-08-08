"""Help widget shown above the status bar."""

from rich.style import Style
from rich.text import Text
from textual.events import Click, Resize
from textual.message import Message
from textual.widgets import Static

from zivo.models import HelpBarAction, HelpBarState


class HelpBar(Static):
    """Stable key reference with contextual visual feedback."""

    class ActionClicked(Message):
        """Message emitted when a help-bar item is clicked."""

        def __init__(self, action: HelpBarAction) -> None:
            super().__init__()
            self.action = action

    def __init__(
        self,
        state: HelpBarState,
        *,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(Text(state.text), id=id, classes=classes)
        self.state = state

    def on_mount(self) -> None:
        self._refresh_render()

    def on_resize(self, _event: Resize) -> None:
        self._refresh_render()

    def on_click(self, event: Click) -> None:
        """Route clicks through the same key dispatcher as keyboard input."""

        style = event.style
        action_id = style.meta.get("help_action_id") if style is not None else None
        if not isinstance(action_id, str):
            return
        action = next(
            (candidate for candidate in self.state.actions if candidate.action_id == action_id),
            None,
        )
        if action is None:
            return
        event.stop()
        self.post_message(self.ActionClicked(action))

    def set_state(self, state: HelpBarState) -> None:
        """Update help content while preserving stable item order."""

        if state == self.state:
            return
        self.state = state
        self._refresh_render()

    def _refresh_render(self) -> None:
        if not self.state.actions:
            self.update(Text(self.state.text))
            return
        self.update(self._render_actions(self.state.actions))

    @staticmethod
    def _render_actions(actions: tuple[HelpBarAction, ...]) -> Text:
        rows: dict[int, list[HelpBarAction]] = {}
        for action in actions:
            rows.setdefault(action.line_index, []).append(action)

        rendered = Text()
        for row_index, row_actions in enumerate(rows.values()):
            if row_index:
                rendered.append("\n")
            for item_index, action in enumerate(row_actions):
                if item_index:
                    rendered.append(" | ")
                rendered.append(
                    action.text,
                    style=HelpBar._style_for(action, action_id=action.action_id),
                )
        return rendered

    @staticmethod
    def _style_for(action: HelpBarAction, *, action_id: str) -> Style:
        if not action.enabled:
            return Style(color="bright_black", dim=True, meta={"help_action_id": action_id})
        if action.emphasized:
            return Style(color="cyan", bold=True, meta={"help_action_id": action_id})
        return Style(color="bright_white", meta={"help_action_id": action_id})
