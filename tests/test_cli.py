from types import SimpleNamespace

import peneo.__main__ as cli
from peneo.models import AppConfig, BehaviorConfig, ConfigLoadResult


class DummyApp:
    def __init__(
        self,
        *,
        return_code: int = 0,
        return_value: str | None = None,
        current_path: str = "/tmp/fallback",
    ) -> None:
        self.return_code = return_code
        self.return_value = return_value
        self.app_state = SimpleNamespace(current_path=current_path)
        self.run_calls = 0

    def run(self) -> None:
        self.run_calls += 1


def test_render_shell_init_outputs_peneo_cd_function() -> None:
    output = cli.render_shell_init("bash")

    assert "peneo-cd()" in output
    assert 'command peneo --print-last-dir "$@"' in output
    assert 'builtin cd -- "$target"' in output


def test_main_print_last_dir_outputs_return_value(capsys, monkeypatch) -> None:
    app = DummyApp(return_value="/tmp/peneo-last-dir")
    monkeypatch.setattr(cli, "load_app_config", lambda: ConfigLoadResult(config=AppConfig()))
    monkeypatch.setattr(cli, "create_app", lambda **_kwargs: app)

    return_code = cli.main(["--print-last-dir"])

    assert return_code == 0
    assert app.run_calls == 1
    assert capsys.readouterr().out == "/tmp/peneo-last-dir\n"


def test_main_print_last_dir_falls_back_to_current_path(capsys, monkeypatch) -> None:
    app = DummyApp(return_value=None, current_path="/tmp/peneo-fallback")
    monkeypatch.setattr(cli, "load_app_config", lambda: ConfigLoadResult(config=AppConfig()))
    monkeypatch.setattr(cli, "create_app", lambda **_kwargs: app)

    return_code = cli.main(["--print-last-dir"])

    assert return_code == 0
    assert app.run_calls == 1
    assert capsys.readouterr().out == "/tmp/peneo-fallback\n"


def test_main_passes_loaded_config_and_warnings_to_create_app(monkeypatch) -> None:
    app = DummyApp()
    loaded_config = AppConfig(behavior=BehaviorConfig(confirm_delete=False))
    captured_kwargs: dict[str, object] = {}

    monkeypatch.setattr(
        cli,
        "load_app_config",
        lambda: ConfigLoadResult(
            config=loaded_config,
            warnings=("using test config",),
        ),
    )

    def fake_create_app(**kwargs):
        captured_kwargs.update(kwargs)
        return app

    monkeypatch.setattr(cli, "create_app", fake_create_app)

    return_code = cli.main([])

    assert return_code == 0
    assert app.run_calls == 1
    assert captured_kwargs["app_config"] is loaded_config
    assert captured_kwargs["config_path"] == ""
    assert captured_kwargs["startup_notification"] is not None
    assert captured_kwargs["startup_notification"].level == "warning"
    assert "using test config" in captured_kwargs["startup_notification"].message


def test_config_warning_notification_returns_warning_message() -> None:
    notification = cli._config_warning_notification(("bad display.default_sort_field",))

    assert notification is not None
    assert notification.level == "warning"
    assert "bad display.default_sort_field" in notification.message
