"""Help widget shown above the status bar."""

from rich.cells import cell_len
from rich.style import Style
from rich.text import Text
from textual.events import Click, Resize
from textual.message import Message
from textual.widgets import Static

from zivo.models import HelpBarAction, HelpBarState


class HelpBar(Static):
    """Contextual actions shown above the status bar."""

    class ActionClicked(Message):
        """Message emitted when a contextual action is clicked."""

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
        """Render the initial state after the widget has a terminal region."""

        if self.state.actions or self.state.discovery_actions:
            self.update(self._render_state(self.state))

    def on_click(self, event: Click) -> None:
        """Emit the clicked action without executing filesystem behavior."""

        action_id = event.style.meta.get("help_action_id")
        if not isinstance(action_id, str):
            return
        action = next(
            (
                candidate
                for candidate in (*self.state.actions, *self.state.discovery_actions)
                if candidate.action_id == action_id
            ),
            None,
        )
        if action is None:
            return
        event.stop()
        self.post_message(self.ActionClicked(action))

    def on_resize(self, _event: Resize) -> None:
        """Reflow actions when the terminal width changes."""

        if self.state.actions or self.state.discovery_actions:
            self.update(self._render_state(self.state))

    def set_state(self, state: HelpBarState) -> None:
        """Update the rendered help line."""

        if state == self.state and not (state.actions or state.discovery_actions):
            return
        self.state = state
        self.update(self._render_state(state))

    def _render_state(self, state: HelpBarState) -> Text:
        if not (state.actions or state.discovery_actions):
            return Text(state.text)

        width = self.content_region.width or self.size.width
        if width <= 0:
            return Text(state.text)

        rows = []
        if state.actions:
            rows.append(self._fit_actions(state.actions, width))
        if state.discovery_actions:
            rows.append(self._fit_actions(state.discovery_actions, width))

        rendered = Text()
        for row_index, row in enumerate(rows):
            if row_index:
                rendered.append("\n")
            for index, action in enumerate(row):
                if index:
                    rendered.append(" | ")
                rendered.append(
                    action.text,
                    style=Style(meta={"help_action_id": action.action_id}),
                )
        return rendered

    @staticmethod
    def _fit_actions(
        actions: tuple[HelpBarAction, ...],
        width: int,
    ) -> tuple[HelpBarAction, ...]:
        """Return the highest-priority actions that fit in the available width."""

        ordered_actions = tuple(sorted(actions, key=lambda action: action.priority))
        more = next(
            (action for action in ordered_actions if action.action_id == "command_palette"),
            None,
        )
        paste = next(
            (action for action in ordered_actions if action.action_id == "paste_clipboard"),
            None,
        )
        tail = more or paste
        candidates = tuple(action for action in ordered_actions if action is not tail)
        selected: list[HelpBarAction] = []

        def fits(items: list[HelpBarAction]) -> bool:
            return cell_len(" | ".join(action.text for action in items)) <= width

        for action in candidates:
            trial = [*selected, action]
            max_candidates = 4 if more is not None else 5
            tail_items = [*trial, tail] if tail is not None else trial
            if len(trial) <= max_candidates and fits(tail_items):
                selected.append(action)

        if more is None and paste is None:
            return tuple(selected)

        if tail is None:
            return tuple(selected)
        while selected and not fits([*selected, tail]):
            selected.pop()
        if not fits([tail]):
            return (tail,)
        selected.append(tail)
        return tuple(selected)
