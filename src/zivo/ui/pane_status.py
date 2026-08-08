"""Rendering helpers for explicit empty, loading, and fallback pane states."""

from rich.style import Style
from rich.text import Text

from zivo.models import MetadataItemViewState, PaneStatusViewState


def render_pane_status(
    state: PaneStatusViewState | None,
    metadata: tuple[MetadataItemViewState, ...] = (),
) -> Text:
    text = Text()
    if state is None:
        return text
    text.append(state.title, style="bold")
    if state.detail:
        text.append(f"\n{state.detail}", style="dim")
    for item in metadata:
        text.append(f"\n{item.label}: ", style="dim")
        text.append(item.value)
    if state.actions:
        text.append("\n\n")
        for index, action in enumerate(state.actions):
            if index:
                text.append("  ")
            text.append(
                f"[{action.label}]",
                style=Style(bold=True, underline=True, meta={"pane_action_id": action.action_id}),
            )
    return text
