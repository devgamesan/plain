from pathlib import Path

from zivo.models import (
    AppConfig,
    BehaviorConfig,
    BookmarkConfig,
    DisplayConfig,
    EditorConfig,
    LoggingConfig,
    TerminalConfig,
)
from zivo.services.config import AppConfigLoader, LiveConfigSaveService, resolve_config_path
from zivo.theme_support import SUPPORTED_APP_THEMES, SUPPORTED_PREVIEW_SYNTAX_THEMES


def test_resolve_config_path_uses_xdg_directory(tmp_path) -> None:
    path = resolve_config_path(
        system_name_resolver=lambda: "Linux",
        environment_variable=lambda name: str(tmp_path) if name == "XDG_CONFIG_HOME" else None,
        home_directory_resolver=lambda: Path("/unused-home"),
    )

    assert path == tmp_path / "zivo" / "config.toml"


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
    assert 'preview_syntax_theme = "auto"' in written
    assert "show_directory_sizes = true" in written
    assert "show_preview = true" in written
    assert 'default_sort_field = "name"' in written
    assert "[logging]" in written
    assert "enabled = true" in written
    assert 'path = ""' in written
    assert '# paths = ["/home/user/src", "/home/user/docs"]' in written
    assert "grep_preview_context_lines = 3" in written


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
        show_directory_sizes = true
        show_preview = false
        theme = "dracula"
        preview_syntax_theme = "one-dark"
        default_sort_field = "modified"
        default_sort_descending = true
        directories_first = false
        grep_preview_context_lines = 5

        [behavior]
        confirm_delete = false
        paste_conflict_action = "rename"

        [logging]
        enabled = false
        path = "~/logs/zivo.log"

        [bookmarks]
        paths = ["/tmp/project", "~/notes", "/tmp/project"]
        """,
        encoding="utf-8",
    )

    result = AppConfigLoader(config_path_resolver=lambda: config_path).load()

    assert result.created is False
    assert result.warnings == ()
    assert result.config.terminal.linux == ("konsole --working-directory {path}",)
    assert result.config.editor.command == "nvim -u NONE"
    assert result.config.display.show_hidden_files is True
    assert result.config.display.show_directory_sizes is True
    assert result.config.display.show_preview is False
    assert result.config.display.theme == "dracula"
    assert result.config.display.preview_syntax_theme == "one-dark"
    assert result.config.display.default_sort_field == "modified"
    assert result.config.display.default_sort_descending is True
    assert result.config.display.directories_first is False
    assert result.config.display.grep_preview_context_lines == 5
    assert result.config.display.split_terminal_position == "bottom"
    assert result.config.behavior.confirm_delete is False
    assert result.config.behavior.paste_conflict_action == "rename"
    assert result.config.logging.enabled is False
    assert result.config.logging.path == "~/logs/zivo.log"
    assert result.config.bookmarks.paths == (
        str(Path("/tmp/project").resolve()),
        str((Path.home() / "notes").resolve()),
    )


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
        show_directory_sizes = "yes"
        show_preview = "yes"
        theme = "bad-theme"
        preview_syntax_theme = "bad-preview-style"
        default_sort_field = "invalid"
        grep_preview_context_lines = -1

        [behavior]
        confirm_delete = "yes"
        paste_conflict_action = "explode"

        [logging]
        enabled = "yes"
        path = 123

        [bookmarks]
        paths = ["relative/path", 3]
        """,
        encoding="utf-8",
    )

    result = AppConfigLoader(config_path_resolver=lambda: config_path).load()

    assert result.config.terminal.linux == ("konsole --working-directory {path}",)
    assert result.config.editor.command is None
    assert result.config.display.show_hidden_files is True
    assert result.config.display.show_directory_sizes is True
    assert result.config.display.show_preview is True
    assert result.config.display.theme == "textual-dark"
    assert result.config.display.preview_syntax_theme == "auto"
    assert result.config.display.default_sort_field == "name"
    assert result.config.behavior.confirm_delete is True
    assert result.config.behavior.paste_conflict_action == "prompt"
    assert result.config.logging.enabled is True
    assert result.config.logging.path is None
    assert result.config.bookmarks.paths == ()
    assert len(result.warnings) == 14


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
    config_path = tmp_path / "zivo" / "config.toml"
    service = LiveConfigSaveService()

    saved_path = service.save(
        path=str(config_path),
        config=AppConfig(
            terminal=TerminalConfig(linux=("konsole --working-directory {path}",)),
            editor=EditorConfig(command="nvim -u NONE"),
            display=DisplayConfig(
                show_hidden_files=True,
                show_directory_sizes=True,
                show_preview=False,
                theme="tokyo-night",
                preview_syntax_theme="one-dark",
                default_sort_field="size",
                default_sort_descending=True,
                directories_first=False,
                grep_preview_context_lines=7,
            ),
            behavior=BehaviorConfig(
                confirm_delete=False,
                paste_conflict_action="rename",
            ),
            logging=LoggingConfig(
                enabled=False,
                path="/tmp/zivo-errors.log",
            ),
            bookmarks=BookmarkConfig(paths=("/tmp/project", "/tmp/docs")),
        ),
    )

    assert saved_path == str(config_path)
    written = config_path.read_text(encoding="utf-8")
    assert '# macos = ["open -a Terminal {path}"]' in written
    assert '# windows = ["wt -d {path}"]' in written
    assert 'linux = ["konsole --working-directory {path}"]' in written
    assert 'command = "nvim -u NONE"' in written
    assert "show_hidden_files = true" in written
    assert "show_directory_sizes = true" in written
    assert "show_preview = false" in written
    assert 'theme = "tokyo-night"' in written
    assert 'preview_syntax_theme = "one-dark"' in written
    assert 'default_sort_field = "size"' in written
    assert "confirm_delete = false" in written
    assert 'paste_conflict_action = "rename"' in written
    assert "enabled = false" in written
    assert 'path = "/tmp/zivo-errors.log"' in written
    assert 'paths = ["/tmp/project", "/tmp/docs"]' in written
    assert "grep_preview_context_lines = 7" in written
    assert 'split_terminal_position = "bottom"' in written


def test_loader_accepts_all_supported_builtin_themes(tmp_path) -> None:
    config_path = tmp_path / "config.toml"

    for theme_name in SUPPORTED_APP_THEMES:
        config_path.write_text(
            f"""
            [display]
            theme = "{theme_name}"
            """,
            encoding="utf-8",
        )

        result = AppConfigLoader(config_path_resolver=lambda: config_path).load()

        assert result.warnings == ()
        assert result.config.display.theme == theme_name


def test_loader_accepts_all_supported_preview_syntax_themes(tmp_path) -> None:
    config_path = tmp_path / "config.toml"

    for theme_name in SUPPORTED_PREVIEW_SYNTAX_THEMES:
        config_path.write_text(
            f"""
            [display]
            preview_syntax_theme = "{theme_name}"
            """,
            encoding="utf-8",
        )

        result = AppConfigLoader(config_path_resolver=lambda: config_path).load()

        assert result.warnings == ()
        assert result.config.display.preview_syntax_theme == theme_name


def test_loader_treats_blank_logging_path_as_default(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
        [logging]
        path = "   "
        """,
        encoding="utf-8",
    )

    result = AppConfigLoader(config_path_resolver=lambda: config_path).load()

    assert result.config.logging.enabled is True
    assert result.config.logging.path is None


def test_loader_rejects_non_integer_grep_preview_context_lines(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
        [display]
        grep_preview_context_lines = "many"
        """,
        encoding="utf-8",
    )

    result = AppConfigLoader(config_path_resolver=lambda: config_path).load()

    assert result.config.display.grep_preview_context_lines == 3
    assert any(
        "display.grep_preview_context_lines must be an integer" in w
        for w in result.warnings
    )


def test_loader_accepts_zero_grep_preview_context_lines(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
        [display]
        grep_preview_context_lines = 0
        """,
        encoding="utf-8",
    )

    result = AppConfigLoader(config_path_resolver=lambda: config_path).load()

    assert result.warnings == ()
    assert result.config.display.grep_preview_context_lines == 0


def test_loader_reads_split_terminal_position(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
        [display]
        split_terminal_position = "right"
        """,
        encoding="utf-8",
    )

    result = AppConfigLoader(config_path_resolver=lambda: config_path).load()

    assert result.warnings == ()
    assert result.config.display.split_terminal_position == "right"


def test_loader_reads_overlay_split_terminal_position(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
        [display]
        split_terminal_position = "overlay"
        """,
        encoding="utf-8",
    )

    result = AppConfigLoader(config_path_resolver=lambda: config_path).load()

    assert result.warnings == ()
    assert result.config.display.split_terminal_position == "overlay"


def test_loader_rejects_invalid_split_terminal_position(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
        [display]
        split_terminal_position = "top"
        """,
        encoding="utf-8",
    )

    result = AppConfigLoader(config_path_resolver=lambda: config_path).load()

    assert len(result.warnings) == 1
    assert "split_terminal_position" in result.warnings[0]
    assert result.config.display.split_terminal_position == "bottom"
