"""Tests for tab-bar affordances."""

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
