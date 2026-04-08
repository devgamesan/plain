from unittest.mock import patch

from peneo.__main__ import main


def test_main_runs_app() -> None:
    with patch("peneo.__main__.create_app") as create_app:
        app = create_app.return_value

        main([])

    app.run.assert_called_once_with(mouse=False)
