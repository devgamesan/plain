from types import SimpleNamespace

import pytest

import peneo.__main__ as cli
from peneo.models import AppConfig, BehaviorConfig, ConfigLoadResult, LoggingConfig
from peneo.services.logging import LoggingSetupResult


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

    def run(self, *, mouse: bool = True) -> None:
        self.run_calls += 1


def test_render_shell_init_outputs_peneo_cd_function() -> None:
    output = cli.render_shell_init("bash")

    assert "peneo-cd()" in output
    assert 'command peneo --print-last-dir "$@"' in output
    assert 'builtin cd -- "$target"' in output


def test_main_print_last_dir_outputs_return_value(capsys, monkeypatch) -> None:
    app = DummyApp(return_value="/tmp/peneo-last-dir")
    monkeypatch.setattr(cli, "load_app_config", lambda: ConfigLoadResult(config=AppConfig()))
    monkeypatch.setattr(
        cli,
        "configure_file_logging",
        lambda **_kwargs: LoggingSetupResult(enabled=True, path="/tmp/peneo.log"),
    )
    monkeypatch.setattr(cli, "create_app", lambda **_kwargs: app)

    return_code = cli.main(["--print-last-dir"])

    assert return_code == 0
    assert app.run_calls == 1
    assert capsys.readouterr().out == "/tmp/peneo-last-dir\n"


def test_main_print_last_dir_falls_back_to_current_path(capsys, monkeypatch) -> None:
    app = DummyApp(return_value=None, current_path="/tmp/peneo-fallback")
    monkeypatch.setattr(cli, "load_app_config", lambda: ConfigLoadResult(config=AppConfig()))
    monkeypatch.setattr(
        cli,
        "configure_file_logging",
        lambda **_kwargs: LoggingSetupResult(enabled=True, path="/tmp/peneo.log"),
    )
    monkeypatch.setattr(cli, "create_app", lambda **_kwargs: app)

    return_code = cli.main(["--print-last-dir"])

    assert return_code == 0
    assert app.run_calls == 1
    assert capsys.readouterr().out == "/tmp/peneo-fallback\n"


def test_main_passes_loaded_config_and_warnings_to_create_app(monkeypatch) -> None:
    app = DummyApp()
    loaded_config = AppConfig(
        behavior=BehaviorConfig(confirm_delete=False),
        logging=LoggingConfig(path="/tmp/custom-peneo.log"),
    )
    captured_kwargs: dict[str, object] = {}
    captured_logging_kwargs: dict[str, object] = {}

    monkeypatch.setattr(
        cli,
        "load_app_config",
        lambda: ConfigLoadResult(
            config=loaded_config,
            warnings=("using test config",),
        ),
    )

    def fake_configure_file_logging(**kwargs):
        captured_logging_kwargs.update(kwargs)
        return LoggingSetupResult(enabled=True, path="/tmp/custom-peneo.log")

    monkeypatch.setattr(cli, "configure_file_logging", fake_configure_file_logging)

    def fake_create_app(**kwargs):
        captured_kwargs.update(kwargs)
        return app

    monkeypatch.setattr(cli, "create_app", fake_create_app)

    return_code = cli.main([])

    assert return_code == 0
    assert app.run_calls == 1
    assert captured_logging_kwargs["config"] is loaded_config.logging
    assert captured_logging_kwargs["config_path"] == ""
    assert captured_kwargs["app_config"] is loaded_config
    assert captured_kwargs["config_path"] == ""
    assert captured_kwargs["startup_notification"] is not None
    assert captured_kwargs["startup_notification"].level == "warning"
    assert "using test config" in captured_kwargs["startup_notification"].message


def test_startup_notification_returns_warning_message() -> None:
    notification = cli._startup_notification(("bad display.default_sort_field",), "")

    assert notification is not None
    assert notification.level == "warning"
    assert "bad display.default_sort_field" in notification.message


def test_main_logs_and_reraises_runtime_exception(monkeypatch) -> None:
    app = DummyApp()

    def raise_in_run() -> None:
        raise RuntimeError("boom")

    app.run = lambda **_kwargs: raise_in_run()  # type: ignore[method-assign]
    monkeypatch.setattr(cli, "load_app_config", lambda: ConfigLoadResult(config=AppConfig()))
    monkeypatch.setattr(
        cli,
        "configure_file_logging",
        lambda **_kwargs: LoggingSetupResult(enabled=True, path="/tmp/peneo.log"),
    )
    monkeypatch.setattr(cli, "create_app", lambda **_kwargs: app)

    captured: list[str] = []

    class DummyLogger:
        def exception(self, message: str) -> None:
            captured.append(message)

    monkeypatch.setattr(cli, "_app_logger", lambda: DummyLogger())

    with pytest.raises(RuntimeError, match="boom"):
        cli.main([])

    assert captured == ["Peneo crashed during startup or runtime"]


def test_startup_notification_includes_logging_warning() -> None:
    notification = cli._startup_notification((), "Failed to initialize log file output")

    assert notification is not None
    assert notification.level == "warning"
    assert "Failed to initialize log file output" in notification.message
