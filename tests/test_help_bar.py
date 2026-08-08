from rich.console import Console
from rich.text import Text

from zivo.models import HelpBarAction
from zivo.ui.help_bar import HelpBar


def test_help_bar_renders_all_stable_actions_without_priority_elision() -> None:
    actions = (
        HelpBarAction("first", "a", "First", 0),
        HelpBarAction("second", "b", "Second", 0, emphasized=True),
        HelpBarAction("third", "c", "Third", 1, enabled=False),
    )

    rendered = HelpBar._render_actions(actions)

    assert isinstance(rendered, Text)
    assert rendered.plain == "a First | b Second\nc Third"


def test_help_bar_action_styles_keep_click_metadata_for_disabled_items() -> None:
    action = HelpBarAction(
        "paste_clipboard",
        "v",
        "paste",
        0,
        enabled=False,
        disabled_reason="Clipboard is empty",
    )

    rendered = HelpBar._render_actions((action,))
    style = rendered.get_style_at_offset(Console(), 0)

    assert style is not None
    assert style.dim is True
    assert style.meta == {"help_action_id": "paste_clipboard"}
