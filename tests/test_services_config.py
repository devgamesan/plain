from pathlib import Path

from peneo.models import AppConfig, BehaviorConfig, DisplayConfig, EditorConfig, TerminalConfig
from peneo.services.config import AppConfigLoader, LiveConfigSaveService, resolve_config_path


def test_resolve_config_path_uses_xdg_directory(tmp_path) -> None:
    path = resolve_config_path(
        system_name_resolver=lambda: "Linux",
        environment_variable=lambda name: str(tmp_path) if name == "XDG_CONFIG_HOME" else None,
        home_directory_resolver=lambda: Path("/unused-home"),
    )

    assert path == tmp_path / "peneo" / "config.toml"


def test_loader_creates_default_config_when_missing(tmp_path) -> None:
    config_path = tmp_path / "config.toml"

    result = AppConfigLoader(config_path_resolver=lambda: config_path).load()

    assert result.created is True
    assert result.config.display.show_hidden_files is False
    assert config_path.exists()
    written = config_path.read_text(encoding="utf-8")
    assert '# linux = [' in written
    assert '#   "konsole --working-directory {path}",' in written
    assert '#   "gnome-terminal --working-directory={path}",' in written
    assert '# command = "nvim -u NONE"' in written
    assert 'theme = "textual-dark"' in written
    assert 'default_sort_field = "name"' in written


def test_loader_reads_valid_config_values(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
        [terminal]
        linux = ["konsole --working-directory {path}"]

        [editor]
        command = "nvim -u NONE"

        [display]
        show_hidden_files = true
        theme = "textual-light"
        default_sort_field = "modified"
        default_sort_descending = true
        directories_first = false

        [behavior]
        confirm_delete = false
        paste_conflict_action = "rename"
        """,
        encoding="utf-8",
    )

    result = AppConfigLoader(config_path_resolver=lambda: config_path).load()

    assert result.created is False
    assert result.warnings == ()
    assert result.config.terminal.linux == ("konsole --working-directory {path}",)
    assert result.config.editor.command == "nvim -u NONE"
    assert result.config.display.show_hidden_files is True
    assert result.config.display.theme == "textual-light"
    assert result.config.display.default_sort_field == "modified"
    assert result.config.display.default_sort_descending is True
    assert result.config.display.directories_first is False
    assert result.config.behavior.confirm_delete is False
    assert result.config.behavior.paste_conflict_action == "rename"


def test_loader_keeps_valid_values_and_warns_for_invalid_entries(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
        [terminal]
        linux = ["konsole --working-directory {path}", "{broken"]

        [editor]
        command = "code --wait"

        [display]
        show_hidden_files = true
        theme = "bad-theme"
        default_sort_field = "invalid"

        [behavior]
        confirm_delete = "yes"
        paste_conflict_action = "explode"
        """,
        encoding="utf-8",
    )

    result = AppConfigLoader(config_path_resolver=lambda: config_path).load()

    assert result.config.terminal.linux == ("konsole --working-directory {path}",)
    assert result.config.editor.command is None
    assert result.config.display.show_hidden_files is True
    assert result.config.display.theme == "textual-dark"
    assert result.config.display.default_sort_field == "name"
    assert result.config.behavior.confirm_delete is True
    assert result.config.behavior.paste_conflict_action == "prompt"
    assert len(result.warnings) == 6


def test_loader_warns_for_invalid_editor_command_syntax(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
        [editor]
        command = "'"
        """,
        encoding="utf-8",
    )

    result = AppConfigLoader(config_path_resolver=lambda: config_path).load()

    assert result.config.editor.command is None
    assert result.warnings == (
        "editor.command is not a valid shell-style command: No closing quotation; using default.",
    )


def test_config_save_service_writes_normalized_config_file(tmp_path) -> None:
    config_path = tmp_path / "peneo" / "config.toml"
    service = LiveConfigSaveService()

    saved_path = service.save(
        path=str(config_path),
        config=AppConfig(
            terminal=TerminalConfig(linux=("konsole --working-directory {path}",)),
            editor=EditorConfig(command="nvim -u NONE"),
            display=DisplayConfig(
                show_hidden_files=True,
                theme="textual-light",
                default_sort_field="size",
                default_sort_descending=True,
                directories_first=False,
            ),
            behavior=BehaviorConfig(
                confirm_delete=False,
                paste_conflict_action="rename",
            ),
        ),
    )

    assert saved_path == str(config_path)
    written = config_path.read_text(encoding="utf-8")
    assert '# macos = ["open -a Terminal {path}"]' in written
    assert '# windows = ["wt -d {path}"]' in written
    assert 'linux = ["konsole --working-directory {path}"]' in written
    assert 'command = "nvim -u NONE"' in written
    assert "show_hidden_files = true" in written
    assert 'theme = "textual-light"' in written
    assert 'default_sort_field = "size"' in written
    assert "confirm_delete = false" in written
    assert 'paste_conflict_action = "rename"' in written
