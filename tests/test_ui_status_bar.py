import pytest
from rich.console import Console
from rich.style import Style
from textual.app import App, ComposeResult

from zivo.models import StatusBarActionState, StatusBarState
from zivo.ui import StatusBar


class _StatusBarTestApp(App[None]):
    def __init__(self) -> None:
        super().__init__()
        self.dismissed_revisions: list[int] = []
        self.clicked_actions: list[tuple[str, int]] = []

    def compose(self) -> ComposeResult:
        yield StatusBar(StatusBarState(), id="status-bar")

    async def on_status_bar_auto_dismiss(self, message: StatusBar.AutoDismiss) -> None:
        self.dismissed_revisions.append(message.revision)

    async def on_status_bar_action_clicked(self, message: StatusBar.ActionClicked) -> None:
        self.clicked_actions.append((message.action_id, message.revision))


class _ActionClick:
    def __init__(self, style: Style) -> None:
        self.style = style
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


@pytest.mark.asyncio
async def test_status_bar_starts_five_second_timer_for_final_success() -> None:
    app = _StatusBarTestApp()

    async with app.run_test() as pilot:
        status_bar = app.query_one("#status-bar", StatusBar)
        status_bar.set_state(
            StatusBarState(
                message="Copied 1 item(s)",
                message_level="info",
                notification_revision=12,
                auto_dismiss=True,
            )
        )
        await pilot.pause(5.1)

    assert app.dismissed_revisions == [12]


@pytest.mark.asyncio
async def test_status_bar_restarts_timer_when_revision_changes_with_same_content() -> None:
    app = _StatusBarTestApp()

    async with app.run_test() as pilot:
        status_bar = app.query_one("#status-bar", StatusBar)
        status_bar.set_state(
            StatusBarState(
                message="Done",
                message_level="info",
                notification_revision=1,
                auto_dismiss=True,
            )
        )
        await pilot.pause(4.0)
        status_bar.set_state(
            StatusBarState(
                message="Done",
                message_level="info",
                notification_revision=2,
                auto_dismiss=True,
            )
        )
        await pilot.pause(1.5)
        assert app.dismissed_revisions == []
        await pilot.pause(3.8)

    assert app.dismissed_revisions == [2]


@pytest.mark.asyncio
async def test_status_bar_keeps_warning_error_and_partial_notifications() -> None:
    app = _StatusBarTestApp()

    async with app.run_test() as pilot:
        status_bar = app.query_one("#status-bar", StatusBar)
        for revision, level, message in (
            (1, "warning", "Copied 1/2 items with 1 failure(s)"),
            (2, "error", "Paste failed"),
            (3, "info", "Skipped 1 conflicting item(s)"),
        ):
            status_bar.set_state(
                StatusBarState(
                    message=message,
                    message_level=level,
                    notification_revision=revision,
                    auto_dismiss=False,
                )
            )
            assert status_bar._auto_dismiss_timer is None
        await pilot.pause(5.1)

    assert app.dismissed_revisions == []


@pytest.mark.asyncio
async def test_status_bar_click_dispatches_stable_action_and_revision() -> None:
    app = _StatusBarTestApp()

    async with app.run_test():
        status_bar = app.query_one("#status-bar", StatusBar)
        click = _ActionClick(
            Style(
                meta={
                    "notification_action_id": "notification.retry",
                    "notification_revision": 9,
                }
            )
        )
        await status_bar.on_click(click)

    assert click.stopped is True
    assert app.clicked_actions == [("notification.retry", 9)]


@pytest.mark.asyncio
async def test_narrow_status_bar_reserves_action_label_and_keeps_click_metadata() -> None:
    app = _StatusBarTestApp()

    async with app.run_test(size=(28, 8)) as pilot:
        status_bar = app.query_one("#status-bar", StatusBar)
        status_bar.set_state(
            StatusBarState(
                message="A very long completed operation message",
                message_level="info",
                action=StatusBarActionState(
                    action_id="notification.retry",
                    label="Retry",
                ),
                notification_revision=11,
                auto_dismiss=False,
            )
        )
        await pilot.pause()
        rendered = status_bar.renderable
        assert rendered.plain.endswith("   Retry")
        meta = rendered.get_style_at_offset(Console(), len(rendered.plain) - 2).meta
        assert meta == {
            "notification_action_id": "notification.retry",
            "notification_revision": 11,
        }
        click = _ActionClick(Style(meta=meta))
        await status_bar.on_click(click)

    assert click.stopped is True
    assert app.clicked_actions == [("notification.retry", 11)]


@pytest.mark.asyncio
async def test_extremely_narrow_status_bar_keeps_action_only_and_clickable() -> None:
    app = _StatusBarTestApp()

    async with app.run_test(size=(4, 8)) as pilot:
        status_bar = app.query_one("#status-bar", StatusBar)
        status_bar.set_state(
            StatusBarState(
                message="A message that cannot fit",
                message_level="error",
                action=StatusBarActionState(
                    action_id="notification.retry",
                    label="Retry",
                ),
                notification_revision=12,
            )
        )
        await pilot.pause()
        rendered = status_bar.renderable
        assert rendered.plain == "Ret…"
        meta = rendered.get_style_at_offset(Console(), len(rendered.plain) - 1).meta
        assert meta == {
            "notification_action_id": "notification.retry",
            "notification_revision": 12,
        }
        click = _ActionClick(Style(meta=meta))
        await status_bar.on_click(click)

    assert click.stopped is True
    assert app.clicked_actions == [("notification.retry", 12)]


def test_status_bar_renders_one_action_with_stable_metadata() -> None:
    rendered = StatusBar._render_state(
        StatusBarState(
            message="Done",
            message_level="info",
            action=StatusBarActionState(
                action_id="notification.undo",
                label="Undo",
            ),
            notification_revision=4,
            auto_dismiss=True,
        )
    )

    assert str(rendered) == "info: Done   Undo"
    assert rendered.get_style_at_offset(Console(), len(rendered.plain) - 2).meta == {
        "notification_action_id": "notification.undo",
        "notification_revision": 4,
    }
