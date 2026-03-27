from types import SimpleNamespace

import peneo.__main__ as cli


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
    monkeypatch.setattr(cli, "create_app", lambda: app)

    return_code = cli.main(["--print-last-dir"])

    assert return_code == 0
    assert app.run_calls == 1
    assert capsys.readouterr().out == "/tmp/peneo-last-dir\n"


def test_main_print_last_dir_falls_back_to_current_path(capsys, monkeypatch) -> None:
    app = DummyApp(return_value=None, current_path="/tmp/peneo-fallback")
    monkeypatch.setattr(cli, "create_app", lambda: app)

    return_code = cli.main(["--print-last-dir"])

    assert return_code == 0
    assert app.run_calls == 1
    assert capsys.readouterr().out == "/tmp/peneo-fallback\n"
