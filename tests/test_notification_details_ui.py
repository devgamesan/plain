import pytest
from textual.containers import VerticalScroll

from zivo import create_app
from zivo.state import (
    NotificationAction,
    NotificationDetails,
    NotificationFailureDetail,
    NotificationState,
)
from zivo.state.actions import ActivateNotificationAction, SetNotification
from zivo.ui import NotificationDetailsDialog


@pytest.mark.asyncio
async def test_details_overlay_renders_failures_and_closes_with_existing_detail_input(
    tmp_path,
) -> None:
    app = create_app(initial_path=tmp_path)
    notification = NotificationState(
        level="warning",
        message="Copied 1/2 items with 1 failure(s)",
        action=NotificationAction(
            action_id="notification.details",
            label="Details",
        ),
        details=NotificationDetails(
            failure_count=1,
            failures=(
                NotificationFailureDetail(
                    path=str(tmp_path / "failed.txt"),
                    reason="permission denied",
                ),
            ),
        ),
    )

    async with app.run_test() as pilot:
        await app.dispatch_actions((SetNotification(notification),))
        await app.dispatch_actions(
            (
                ActivateNotificationAction(
                    "notification.details",
                    app.app_state.notification_revision,
                ),
            )
        )
        dialog = app.query_one(
            "#notification-details-dialog",
            NotificationDetailsDialog,
        )
        assert dialog.display is True
        assert "Failures: 1" in str(
            dialog.query_one("#notification-details-lines").renderable
        )
        assert "permission denied" in str(
            dialog.query_one("#notification-details-lines").renderable
        )

        await pilot.press("escape")

    assert app.app_state.notification_details is None
    assert app.app_state.ui_mode == "BROWSING"


@pytest.mark.asyncio
async def test_details_overlay_scrolls_many_failures_at_narrow_width(tmp_path) -> None:
    app = create_app(initial_path=tmp_path)
    failures = tuple(
        NotificationFailureDetail(
            path=str(tmp_path / f"nested/failed-{index}.txt"),
            reason="permission denied while processing a long filename",
        )
        for index in range(20)
    )
    notification = NotificationState(
        level="warning",
        message="Many failures",
        action=NotificationAction(
            action_id="notification.details",
            label="Details",
        ),
        details=NotificationDetails(
            failure_count=len(failures),
            failures=failures,
        ),
    )

    async with app.run_test(size=(40, 16)) as pilot:
        await app.dispatch_actions((SetNotification(notification),))
        await app.dispatch_actions(
            (
                ActivateNotificationAction(
                    "notification.details",
                    app.app_state.notification_revision,
                ),
            )
        )
        await pilot.pause()
        dialog = app.query_one("#notification-details-dialog", NotificationDetailsDialog)
        scroll = dialog.query_one(
            "#notification-details-lines-scroll",
            VerticalScroll,
        )
        rendered = dialog.query_one("#notification-details-lines").renderable

        assert scroll.max_scroll_y > 0
        assert "failed-0.txt" in str(rendered)
        assert "failed-19.txt" in str(rendered)
