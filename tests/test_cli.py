import io
import sys
from types import SimpleNamespace

import pytest

import zivo.__main__ as cli
from zivo.models import AppConfig, BehaviorConfig, ConfigLoadResult, LoggingConfig
from zivo.services.logging import LoggingSetupResult


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


class DummyTextStream(io.StringIO):
    def __init__(self, *, isatty: bool) -> None:
        super().__init__()
        self._isatty = isatty

    def isatty(self) -> bool:
        return self._isatty


def test_render_shell_init_outputs_zivo_cd_function() -> None:
    output = cli.render_shell_init("bash")

    assert "zivo-cd()" in output
    assert 'command zivo --print-last-dir "$@"' in output
    assert 'builtin cd -- "$target"' in output


def test_main_print_last_dir_outputs_return_value(capsys, monkeypatch) -> None:
    app = DummyApp(return_value="/tmp/zivo-last-dir")
    monkeypatch.setattr(
        "zivo.services.load_app_config",
        lambda: ConfigLoadResult(config=AppConfig()),
    )
    monkeypatch.setattr(
        "zivo.services.configure_file_logging",
        lambda **_kwargs: LoggingSetupResult(enabled=True, path="/tmp/zivo.log"),
    )
    monkeypatch.setattr("zivo.app.create_app", lambda **_kwargs: app)

    return_code = cli.main(["--print-last-dir"])

    assert return_code == 0
    assert app.run_calls == 1
    assert capsys.readouterr().out == "/tmp/zivo-last-dir\n"


def test_main_print_last_dir_falls_back_to_current_path(capsys, monkeypatch) -> None:
    app = DummyApp(return_value=None, current_path="/tmp/zivo-fallback")
    monkeypatch.setattr(
        "zivo.services.load_app_config",
        lambda: ConfigLoadResult(config=AppConfig()),
    )
    monkeypatch.setattr(
        "zivo.services.configure_file_logging",
        lambda **_kwargs: LoggingSetupResult(enabled=True, path="/tmp/zivo.log"),
    )
    monkeypatch.setattr("zivo.app.create_app", lambda **_kwargs: app)

    return_code = cli.main(["--print-last-dir"])

    assert return_code == 0
    assert app.run_calls == 1
    assert capsys.readouterr().out == "/tmp/zivo-fallback\n"


def test_shell_integration_stdio_redirects_standard_streams_to_tty(monkeypatch) -> None:
    original_stdin = DummyTextStream(isatty=True)
    original_stdout = DummyTextStream(isatty=False)
    original_stderr = DummyTextStream(isatty=True)
    tty_stdin = DummyTextStream(isatty=True)
    tty_stdout = DummyTextStream(isatty=True)
    tty_stderr = DummyTextStream(isatty=True)

    monkeypatch.setattr(sys, "stdin", original_stdin)
    monkeypatch.setattr(sys, "stdout", original_stdout)
    monkeypatch.setattr(sys, "stderr", original_stderr)
    monkeypatch.setattr(sys, "__stdin__", original_stdin, raising=False)
    monkeypatch.setattr(sys, "__stdout__", original_stdout, raising=False)
    monkeypatch.setattr(sys, "__stderr__", original_stderr, raising=False)
    monkeypatch.setattr(
        cli,
        "_open_tty_streams",
        lambda: cli._StandardStreams(
            stdin=tty_stdin,
            stdout=tty_stdout,
            stderr=tty_stderr,
        ),
    )

    with cli._shell_integration_stdio(True):
        assert sys.stdin is tty_stdin
        assert sys.stdout is tty_stdout
        assert sys.stderr is tty_stderr
        assert sys.__stdin__ is tty_stdin
        assert sys.__stdout__ is tty_stdout
        assert sys.__stderr__ is tty_stderr

    assert sys.stdin is original_stdin
    assert sys.stdout is original_stdout
    assert sys.stderr is original_stderr
    assert tty_stdin.closed is True
    assert tty_stdout.closed is True
    assert tty_stderr.closed is True


def test_shell_integration_stdio_falls_back_when_tty_open_fails(monkeypatch) -> None:
    original_stdin = DummyTextStream(isatty=True)
    original_stdout = DummyTextStream(isatty=False)
    original_stderr = DummyTextStream(isatty=True)

    monkeypatch.setattr(sys, "stdin", original_stdin)
    monkeypatch.setattr(sys, "stdout", original_stdout)
    monkeypatch.setattr(sys, "stderr", original_stderr)
    monkeypatch.setattr(sys, "__stdin__", original_stdin, raising=False)
    monkeypatch.setattr(sys, "__stdout__", original_stdout, raising=False)
    monkeypatch.setattr(sys, "__stderr__", original_stderr, raising=False)
    monkeypatch.setattr(
        cli,
        "_open_tty_streams",
        lambda: (_ for _ in ()).throw(OSError("/dev/tty unavailable")),
    )

    with cli._shell_integration_stdio(True):
        assert sys.stdin is original_stdin
        assert sys.stdout is original_stdout
        assert sys.stderr is original_stderr


def test_main_print_last_dir_runs_app_with_tty_streams_when_stdout_is_captured(
    monkeypatch,
) -> None:
    original_stdin = DummyTextStream(isatty=True)
    original_stdout = DummyTextStream(isatty=False)
    original_stderr = DummyTextStream(isatty=True)
    tty_stdin = DummyTextStream(isatty=True)
    tty_stdout = DummyTextStream(isatty=True)
    tty_stderr = DummyTextStream(isatty=True)
    app = DummyApp(return_value="/tmp/zivo-last-dir")

    def run_with_tty_streams(*, mouse: bool = True) -> None:
        app.run_calls += 1
        assert mouse is False
        assert sys.stdin is tty_stdin
        assert sys.stdout is tty_stdout
        assert sys.stderr is tty_stderr
        assert sys.__stdout__ is tty_stdout
        assert sys.__stderr__ is tty_stderr

    app.run = run_with_tty_streams  # type: ignore[method-assign]

    monkeypatch.setattr(sys, "stdin", original_stdin)
    monkeypatch.setattr(sys, "stdout", original_stdout)
    monkeypatch.setattr(sys, "stderr", original_stderr)
    monkeypatch.setattr(sys, "__stdin__", original_stdin, raising=False)
    monkeypatch.setattr(sys, "__stdout__", original_stdout, raising=False)
    monkeypatch.setattr(sys, "__stderr__", original_stderr, raising=False)
    monkeypatch.setattr(
        "zivo.services.load_app_config",
        lambda: ConfigLoadResult(config=AppConfig()),
    )
    monkeypatch.setattr(
        "zivo.services.configure_file_logging",
        lambda **_kwargs: LoggingSetupResult(enabled=True, path="/tmp/zivo.log"),
    )
    monkeypatch.setattr("zivo.app.create_app", lambda **_kwargs: app)
    monkeypatch.setattr(
        cli,
        "_open_tty_streams",
        lambda: cli._StandardStreams(
            stdin=tty_stdin,
            stdout=tty_stdout,
            stderr=tty_stderr,
        ),
    )

    return_code = cli.main(["--print-last-dir"])

    assert return_code == 0
    assert app.run_calls == 1
    assert original_stdout.getvalue() == "/tmp/zivo-last-dir\n"
    assert sys.stdout is original_stdout
    assert tty_stdout.closed is True


def test_main_passes_loaded_config_and_warnings_to_create_app(monkeypatch) -> None:
    app = DummyApp()
    loaded_config = AppConfig(
        behavior=BehaviorConfig(confirm_delete=False),
        logging=LoggingConfig(path="/tmp/custom-zivo.log"),
    )
    captured_kwargs: dict[str, object] = {}
    captured_logging_kwargs: dict[str, object] = {}

    monkeypatch.setattr(
        "zivo.services.load_app_config",
        lambda: ConfigLoadResult(
            config=loaded_config,
            warnings=("using test config",),
        ),
    )

    def fake_configure_file_logging(**kwargs):
        captured_logging_kwargs.update(kwargs)
        return LoggingSetupResult(enabled=True, path="/tmp/custom-zivo.log")

    monkeypatch.setattr(
        "zivo.services.configure_file_logging",
        fake_configure_file_logging,
    )

    def fake_create_app(**kwargs):
        captured_kwargs.update(kwargs)
        return app

    monkeypatch.setattr("zivo.app.create_app", fake_create_app)

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
    monkeypatch.setattr(
        "zivo.services.load_app_config",
        lambda: ConfigLoadResult(config=AppConfig()),
    )
    monkeypatch.setattr(
        "zivo.services.configure_file_logging",
        lambda **_kwargs: LoggingSetupResult(enabled=True, path="/tmp/zivo.log"),
    )
    monkeypatch.setattr("zivo.app.create_app", lambda **_kwargs: app)

    captured: list[str] = []

    class DummyLogger:
        def exception(self, message: str) -> None:
            captured.append(message)

    monkeypatch.setattr(cli, "_app_logger", lambda: DummyLogger())

    with pytest.raises(RuntimeError, match="boom"):
        cli.main([])

    assert captured == ["zivo crashed during startup or runtime"]


def test_startup_notification_includes_logging_warning() -> None:
    notification = cli._startup_notification((), "Failed to initialize log file output")

    assert notification is not None
    assert notification.level == "warning"
    assert "Failed to initialize log file output" in notification.message
