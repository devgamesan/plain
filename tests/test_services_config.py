from pathlib import Path

from zivo.models import (
    AppConfig,
    BehaviorConfig,
    BookmarkConfig,
    DisplayConfig,
    EditorConfig,
    FileSearchConfig,
    GuiEditorConfig,
    HelpBarConfig,
    LoggingConfig,
    TerminalConfig,
)
from zivo.services.config import (
    AppConfigLoader,
    LiveConfigSaveService,
    render_app_config,
    resolve_config_path,
)
from zivo.theme_support import SUPPORTED_APP_THEMES, SUPPORTED_PREVIEW_SYNTAX_THEMES


def test_resolve_config_path_uses_xdg_directory(tmp_path) -> None:
    path = resolve_config_path(
        system_name_resolver=lambda: "Linux",
        environment_variable=lambda name: str(tmp_path) if name == "XDG_CONFIG_HOME" else None,
        home_directory_resolver=lambda: Path("/unused-home"),
    )

    assert path == tmp_path / "zivo" / "config.toml"


def test_resolve_config_path_uses_appdata_on_windows(tmp_path) -> None:
    path = resolve_config_path(
        system_name_resolver=lambda: "Windows",
        environment_variable=lambda name: str(tmp_path) if name == "APPDATA" else None,
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
    assert "[gui_editor]" in written
    assert 'command = "code --goto {path}:{line}:{column}"' in written
    assert 'fallback_command = "code {path}"' in written
    assert 'theme = "textual-dark"' in written
    assert 'preview_syntax_theme = "auto"' in written
    assert "preview_max_kib = 64" in written
    assert "show_directory_sizes = true" in written
    assert "enable_text_preview = true" in written
    assert "enable_image_preview = true" in written
    assert "enable_pdf_preview = true" in written
    assert "enable_office_preview = true" in written
    assert 'default_sort_field = "name"' in written
    assert "[logging]" in written
    assert "enabled = true" in written
    assert 'path = ""' in written
    assert '# paths = ["/home/user/src", "/home/user/docs"]' in written
    assert "grep_preview_context_lines = 3" in written


def test_loader_reads_valid_config_values(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    bookmark_a = str((tmp_path / "project").resolve())
    bookmark_b = str((tmp_path / "notes").resolve())
    bookmark_a_toml = bookmark_a.replace("\\", "\\\\")
    bookmark_b_toml = bookmark_b.replace("\\", "\\\\")
    config_path.write_text(
        f"""
        [terminal]
        linux = ["konsole --working-directory {{path}}"]

        [editor]
        command = "nvim -u NONE"

        [gui_editor]
        command = "codium --goto {{path}}:{{line}}:{{column}}"
        fallback_command = "codium {{path}}"

        [display]
        show_hidden_files = true
        show_directory_sizes = true
        enable_text_preview = false
        enable_image_preview = false
        enable_pdf_preview = false
        enable_office_preview = false
        theme = "dracula"
        preview_syntax_theme = "one-dark"
        preview_max_kib = 256
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
        paths = ["{bookmark_a_toml}", "{bookmark_b_toml}", "{bookmark_a_toml}"]
        """,
        encoding="utf-8",
    )

    result = AppConfigLoader(config_path_resolver=lambda: config_path).load()

    assert result.created is False
    assert result.warnings == ()
    assert result.config.terminal.linux == ("konsole --working-directory {path}",)
    assert result.config.editor.command == "nvim -u NONE"
    assert result.config.gui_editor.command == "codium --goto {path}:{line}:{column}"
    assert result.config.gui_editor.fallback_command == "codium {path}"
    assert result.config.display.show_hidden_files is True
    assert result.config.display.show_directory_sizes is True
    assert result.config.display.enable_text_preview is False
    assert result.config.display.enable_image_preview is False
    assert result.config.display.enable_pdf_preview is False
    assert result.config.display.enable_office_preview is False
    assert result.config.display.theme == "dracula"
    assert result.config.display.preview_syntax_theme == "one-dark"
    assert result.config.display.preview_max_kib == 256
    assert result.config.display.default_sort_field == "modified"
    assert result.config.display.default_sort_descending is True
    assert result.config.display.directories_first is False
    assert result.config.display.grep_preview_context_lines == 5
    assert result.config.behavior.confirm_delete is False
    assert result.config.behavior.paste_conflict_action == "rename"
    assert result.config.logging.enabled is False
    assert result.config.logging.path == "~/logs/zivo.log"
    assert result.config.bookmarks.paths == (bookmark_a, bookmark_b)


def test_loader_keeps_valid_values_and_warns_for_invalid_entries(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
        [terminal]
        linux = ["konsole --working-directory {path}", "{broken"]

        [editor]
        command = "code --wait"

        [gui_editor]
        command = "{bad"
        fallback_command = 1

        [display]
        show_hidden_files = true
        show_directory_sizes = "yes"
        enable_text_preview = "yes"
        enable_image_preview = "yes"
        enable_pdf_preview = "yes"
        enable_office_preview = "yes"
        theme = "bad-theme"
        preview_syntax_theme = "bad-preview-style"
        preview_max_kib = 42
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
    assert result.config.gui_editor == GuiEditorConfig()
    assert result.config.display.show_hidden_files is True
    assert result.config.display.show_directory_sizes is True
    assert result.config.display.enable_text_preview is True
    assert result.config.display.enable_image_preview is True
    assert result.config.display.enable_pdf_preview is True
    assert result.config.display.enable_office_preview is True
    assert result.config.display.theme == "textual-dark"
    assert result.config.display.preview_syntax_theme == "auto"
    assert result.config.display.preview_max_kib == 64
    assert result.config.display.default_sort_field == "name"
    assert result.config.behavior.confirm_delete is True
    assert result.config.behavior.paste_conflict_action == "prompt"
    assert result.config.logging.enabled is True
    assert result.config.logging.path is None
    assert result.config.bookmarks.paths == ()
    assert len(result.warnings) == 20


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
            terminal=TerminalConfig(
                linux=("konsole --working-directory {path}",),
            ),
            editor=EditorConfig(command="nvim -u NONE"),
            gui_editor=GuiEditorConfig(
                command="codium --goto {path}:{line}:{column}",
                fallback_command="codium {path}",
            ),
            display=DisplayConfig(
                show_hidden_files=True,
                show_directory_sizes=True,
                enable_text_preview=False,
                enable_image_preview=False,
                enable_pdf_preview=False,
                enable_office_preview=False,
                theme="tokyo-night",
                preview_syntax_theme="one-dark",
                preview_max_kib=512,
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
    assert 'command = "codium --goto {path}:{line}:{column}"' in written
    assert 'fallback_command = "codium {path}"' in written
    assert "show_hidden_files = true" in written
    assert "show_directory_sizes = true" in written
    assert "enable_text_preview = false" in written
    assert "enable_image_preview = false" in written
    assert "enable_pdf_preview = false" in written
    assert "enable_office_preview = false" in written
    assert 'theme = "tokyo-night"' in written
    assert 'preview_syntax_theme = "one-dark"' in written
    assert "preview_max_kib = 512" in written
    assert 'default_sort_field = "size"' in written
    assert "confirm_delete = false" in written
    assert 'paste_conflict_action = "rename"' in written
    assert "enabled = false" in written
    assert 'path = "/tmp/zivo-errors.log"' in written
    assert 'paths = ["/tmp/project", "/tmp/docs"]' in written
    assert "grep_preview_context_lines = 7" in written


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


def test_loader_reads_preview_max_kib(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
        [display]
        preview_max_kib = 1024
        """,
        encoding="utf-8",
    )

    result = AppConfigLoader(config_path_resolver=lambda: config_path).load()

    assert result.warnings == ()
    assert result.config.display.preview_max_kib == 1024


def test_loader_rejects_invalid_preview_max_kib(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
        [display]
        preview_max_kib = 96
        """,
        encoding="utf-8",
    )

    result = AppConfigLoader(config_path_resolver=lambda: config_path).load()

    assert result.config.display.preview_max_kib == 64
    assert any("display.preview_max_kib" in warning for warning in result.warnings)


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




def test_render_app_config_round_trips_full_config(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    bookmark_paths = (
        str((tmp_path / "project").resolve(strict=False)),
        str((tmp_path / "docs").resolve(strict=False)),
    )
    config = AppConfig(
        terminal=TerminalConfig(
            linux=("konsole --working-directory {path}",),
            macos=("open -a Terminal {path}",),
        ),
        editor=EditorConfig(command="nvim -u NONE"),
        gui_editor=GuiEditorConfig(
            command="codium --goto {path}:{line}:{column}",
            fallback_command="codium {path}",
        ),
        display=DisplayConfig(
            show_hidden_files=True,
            show_directory_sizes=False,
            enable_text_preview=False,
            enable_image_preview=False,
            enable_pdf_preview=False,
            enable_office_preview=False,
            theme="tokyo-night",
            preview_syntax_theme="one-dark",
            preview_max_kib=512,
            default_sort_field="size",
            default_sort_descending=True,
            directories_first=False,
            grep_preview_context_lines=6,
        ),
        behavior=BehaviorConfig(
            confirm_delete=False,
            paste_conflict_action="rename",
        ),
        logging=LoggingConfig(
            enabled=False,
            path="~/logs/zivo.log",
            level="WARNING",
        ),
        bookmarks=BookmarkConfig(paths=bookmark_paths),
        help_bar=HelpBarConfig(
            browsing=("j/k: move", "enter: open"),
            shell=("ctrl+t: terminal",),
        ),
    )
    config_path.write_text(render_app_config(config), encoding="utf-8")

    result = AppConfigLoader(config_path_resolver=lambda: config_path).load()

    assert result.warnings == ()
    assert result.config == config


def test_loader_created_default_config_round_trips_without_warnings(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    loader = AppConfigLoader(config_path_resolver=lambda: config_path)

    created = loader.load()
    reloaded = loader.load()

    assert created.created is True
    assert reloaded.created is False
    assert reloaded.warnings == ()
    assert reloaded.config == AppConfig()


def test_file_search_config_default_is_unlimited() -> None:
    """file_search.max_results のデフォルト値が None であることを確認."""
    config = AppConfig()
    assert config.file_search.max_results is None


def test_file_search_config_custom_max_results() -> None:
    """file_search.max_results にカスタム値を設定できることを確認."""
    config = AppConfig(file_search=FileSearchConfig(max_results=1000))
    assert config.file_search.max_results == 1000


def test_loader_reads_file_search_max_results(tmp_path) -> None:
    """config.toml から file_search.max_results を読み込めることを確認."""
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
        [file_search]
        max_results = 500
        """,
        encoding="utf-8",
    )

    result = AppConfigLoader(config_path_resolver=lambda: config_path).load()

    assert result.warnings == ()
    assert result.config.file_search.max_results == 500


def test_loader_accepts_empty_file_search_section(tmp_path) -> None:
    """file_search セクションが空の場合、制限なしであることを確認."""
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
        [file_search]
        """,
        encoding="utf-8",
    )

    result = AppConfigLoader(config_path_resolver=lambda: config_path).load()

    assert result.warnings == ()
    assert result.config.file_search.max_results is None


def test_loader_rejects_negative_file_search_max_results(tmp_path) -> None:
    """file_search.max_results が負の値の場合、デフォルト値になることを確認."""
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
        [file_search]
        max_results = -100
        """,
        encoding="utf-8",
    )

    result = AppConfigLoader(config_path_resolver=lambda: config_path).load()

    assert result.config.file_search.max_results is None
    assert any(
        "file_search.max_results must be 0 or greater" in w
        for w in result.warnings
    )


def test_loader_rejects_non_integer_file_search_max_results(tmp_path) -> None:
    """file_search.max_results が整数以外の場合、デフォルト値になることを確認."""
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
        [file_search]
        max_results = "unlimited"
        """,
        encoding="utf-8",
    )

    result = AppConfigLoader(config_path_resolver=lambda: config_path).load()

    assert result.config.file_search.max_results is None
    assert any(
        "file_search.max_results must be an integer" in w
        for w in result.warnings
    )


def test_render_app_config_includes_file_search_section(tmp_path) -> None:
    """render_app_config が file_search セクションを出力することを確認."""
    config = AppConfig(
        file_search=FileSearchConfig(max_results=1000),
    )
    rendered = render_app_config(config)

    assert "[file_search]" in rendered
    assert "max_results = 1000" in rendered


def test_render_app_config_shows_comment_for_default_file_search_max_results() -> None:
    """file_search.max_results がデフォルト（None）の場合、コメントで表示されることを確認."""
    config = AppConfig()
    rendered = render_app_config(config)

    assert "[file_search]" in rendered
    assert "# max_results = 1000" in rendered
