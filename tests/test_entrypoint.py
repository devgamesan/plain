from unittest.mock import patch

from zivo.__main__ import main


def test_main_runs_app() -> None:
    with patch("zivo.app.create_app") as create_app:
        app = create_app.return_value

        main([])

    app.run.assert_called_once_with(mouse=False)
