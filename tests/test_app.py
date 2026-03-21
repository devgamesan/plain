import pytest
from textual.widgets import Static

from plain import create_app


def test_create_app_returns_plain_app() -> None:
    app = create_app()

    assert app.title == "Plain"


@pytest.mark.asyncio
async def test_app_can_start_in_headless_mode() -> None:
    app = create_app()

    async with app.run_test():
        message = app.query_one("#message", Static)

    assert str(message.renderable) == "Plain bootstrap is ready."
