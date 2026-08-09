"""Tests for tab-bar affordances."""

from rich.style import Style
from textual import events

from zivo.models import TabBarState, TabItemState
from zivo.ui.tab_bar import TabBar


def _meta_for_text(renderable, substring: str) -> dict:
    for span in renderable.spans:
        if substring in renderable.plain[span.start : span.end] and span.style:
            if span.style.meta:
                return dict(span.style.meta)
    raise AssertionError(f"No metadata for {substring!r}")


def test_tab_bar_renders_new_affordance_and_active_metadata() -> None:
    state = TabBarState(
        (
            TabItemState("one", active=True),
            TabItemState("two"),
        )
    )

    rendered = TabBar._render_state(state, include_new=True)

    assert rendered.plain == "[1:one] [2:two] [+]"
    assert _meta_for_text(rendered, "[1:one]") == {
        "tab_index": 1,
        "tab_action": "activate",
    }
    assert _meta_for_text(rendered, "[+]") == {"tab_action": "new"}


def test_tab_bar_close_affordance_is_separate_from_tab_click() -> None:
    state = TabBarState(
        (
            TabItemState("one"),
            TabItemState("two", active=True),
        )
    )

    rendered = TabBar._render_state(state, hovered_index=2, include_new=True)

    assert rendered.plain == "[1:one] [2:two] × [+]"
    assert _meta_for_text(rendered, "×") == {
        "tab_close_index": 2,
        "tab_action": "close",
    }


def test_tab_bar_narrow_render_prioritizes_active_neighbors() -> None:
    state = TabBarState(
        tuple(
            TabItemState(str(index), active=index == 4)
            for index in range(1, 6)
        )
    )

    rendered = TabBar._render_state(state, include_new=True, max_width=28)

    assert "[4:4]" in rendered.plain
    assert "[3:3]" in rendered.plain
    assert "[5:5]" in rendered.plain
    assert "+2" in rendered.plain or "+1" in rendered.plain


def test_tab_bar_keeps_close_affordance_when_hover_event_has_no_metadata() -> None:
    state = TabBarState(
        (
            TabItemState("one"),
            TabItemState("two", active=True),
        )
    )
    tab_bar = TabBar(state)
    tab_bar._hovered_index = 2
    tab_bar.update(TabBar._render_state(state, hovered_index=2, include_new=True))

    tab_bar.on_mouse_move(
        events.MouseMove(
            widget=tab_bar,
            x=0,
            y=0,
            delta_x=0,
            delta_y=0,
            button=0,
            shift=False,
            meta=False,
            ctrl=False,
            style=Style(),
        )
    )

    assert tab_bar._hovered_index == 2
    assert "×" in tab_bar.renderable.plain


def test_tab_bar_close_click_falls_back_to_rendered_close_span() -> None:
    state = TabBarState(
        (
            TabItemState("one"),
            TabItemState("two", active=True),
        )
    )
    tab_bar = TabBar(state)
    tab_bar._hovered_index = 2
    tab_bar.update(TabBar._render_state(state, hovered_index=2, include_new=True))
    close_x = tab_bar.renderable.plain.index("×")
    messages = []
    tab_bar.post_message = messages.append

    tab_bar.on_click(
        events.Click(
            widget=tab_bar,
            x=close_x,
            y=0,
            delta_x=0,
            delta_y=0,
            button=1,
            shift=False,
            meta=False,
            ctrl=False,
            style=Style(),
        )
    )

    assert len(messages) == 1
    assert isinstance(messages[0], TabBar.TabClosed)
    assert messages[0].tab_index == 1
