from pathlib import Path

from zivo.models import (
    ActionsConfig,
    AppConfig,
    BackgroundCommandConfig,
    BehaviorConfig,
    BookmarkConfig,
    CustomActionConfig,
    DisplayConfig,
    EditorConfig,
    FileSearchConfig,
    GrepSearchConfig,
    GuiEditorConfig,
    LoggingConfig,
    PreviewResourceConfig,
    TerminalConfig,
)
from zivo.models.config_editor import CONFIG_EDITOR_FIELDS
from zivo.services.config import (
    AppConfigLoader,
    LiveConfigSaveService,
    render_app_config,
    resolve_config_path,
)
from zivo.services.config.save import CONFIG_EDITOR_MANAGED_SETTINGS
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
    assert "# Examples: code, codium, cursor, subl, zed, idea, pycharm, webstorm, kate." in written
    assert 'command = "code --goto {path}:{line}:{column}"' in written
    assert 'fallback_command = "code {path}"' in written
    assert 'theme = "textual-dark"' in written
    assert 'preview_syntax_theme = "auto"' in written
    assert "preview_max_kib = 64" in written
    assert "[preview]" in written
    assert "image_stdout_max_mib = 2" in written
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
    assert "[background_commands]" in written
    assert "max_output_kib = 1024" in written
    assert "timeout_seconds = 300" in written


def test_loader_marks_invalid_toml_as_fatal(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text("[display\ntheme = 'dracula'", encoding="utf-8")

    result = AppConfigLoader(config_path_resolver=lambda: config_path).load()

    assert result.fatal is True
    assert result.config == AppConfig()
    assert result.warnings and result.warnings[0].startswith("Failed to parse config.toml:")


def test_config_editor_metadata_is_the_save_source_of_truth() -> None:
    expected_settings = tuple(
        setting
        for field in CONFIG_EDITOR_FIELDS
        for setting in field.managed_settings
    )

    assert CONFIG_EDITOR_MANAGED_SETTINGS == expected_settings
    assert tuple(field.field_id for field in CONFIG_EDITOR_FIELDS) == (
        "editor.command",
        "gui_editor.preset",
        "display.show_hidden_files",
        "display.theme",
        "display.preview_syntax_theme",
        "display.enable_text_preview",
        "display.enable_image_preview",
        "display.enable_pdf_preview",
        "display.enable_office_preview",
        "display.default_sort_field",
        "display.default_sort_descending",
        "display.directories_first",
        "behavior.confirm_delete",
    )


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

        [preview]
        timeout_seconds = 9.5
        stdout_max_kib = 512
        stderr_max_kib = 32
        image_timeout_seconds = 20
        image_stdout_max_mib = 8
        kitty_stdout_max_mib = 64
        input_max_mib = 512
        max_archive_entries = 8192
        max_archive_entry_mib = 128
        max_archive_total_mib = 512
        max_archive_compression_ratio = 200
        timeout_cache_seconds = 2.5

        [behavior]
        confirm_delete = false
        paste_conflict_action = "rename"

        [logging]
        enabled = false
        path = "~/logs/zivo.log"

        [bookmarks]
        paths = ["{bookmark_a_toml}", "{bookmark_b_toml}", "{bookmark_a_toml}"]

        [background_commands]
        max_output_kib = 2048
        timeout_seconds = 900

        [[actions.custom]]
        name = "Optimize PNG"
        command = ["oxipng", "-o", "4", "{{file}}"]
        when = "single_file"
        mode = "background"
        extensions = ["png", ".jpg"]

        [[actions.custom]]
        name = "Open lazygit"
        command = ["lazygit"]
        when = "always"
        mode = "terminal"
        cwd = "{{cwd}}"

        [[actions.custom]]
        name = "Open lazygit in new terminal"
        command = ["lazygit"]
        when = "always"
        mode = "terminal_window"
        cwd = "{{cwd}}"
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
    assert result.config.preview == PreviewResourceConfig(
        timeout_seconds=9.5,
        stdout_max_kib=512,
        stderr_max_kib=32,
        image_timeout_seconds=20.0,
        image_stdout_max_mib=8,
        kitty_stdout_max_mib=64,
        input_max_mib=512,
        max_archive_entries=8192,
        max_archive_entry_mib=128,
        max_archive_total_mib=512,
        max_archive_compression_ratio=200.0,
        timeout_cache_seconds=2.5,
    )
    assert result.config.behavior.confirm_delete is False
    assert result.config.behavior.paste_conflict_action == "rename"
    assert result.config.logging.enabled is False
    assert result.config.logging.path == "~/logs/zivo.log"
    assert result.config.bookmarks.paths == (bookmark_a, bookmark_b)
    assert result.config.background_commands == BackgroundCommandConfig(
        max_output_kib=2048,
        timeout_seconds=900,
    )
    assert result.config.actions.custom == (
        CustomActionConfig(
            name="Optimize PNG",
            command=("oxipng", "-o", "4", "{file}"),
            when="single_file",
            mode="background",
            extensions=("png", "jpg"),
        ),
        CustomActionConfig(
            name="Open lazygit",
            command=("lazygit",),
            when="always",
            mode="terminal",
            cwd="{cwd}",
        ),
        CustomActionConfig(
            name="Open lazygit in new terminal",
            command=("lazygit",),
            when="always",
            mode="terminal_window",
            cwd="{cwd}",
        ),
    )


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

        [background_commands]
        max_output_kib = 4097
        timeout_seconds = 0
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
    assert result.config.background_commands == BackgroundCommandConfig()
    assert len(result.warnings) == 22


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
            background_commands=BackgroundCommandConfig(
                max_output_kib=512,
                timeout_seconds=120,
            ),
            actions=ActionsConfig(
                custom=(
                    CustomActionConfig(
                        name="Open lazygit",
                        command=("lazygit",),
                        when="always",
                        mode="terminal",
                        cwd="{cwd}",
                    ),
                )
            ),
        ),
    )

    assert saved_path == str(config_path)
    written = config_path.read_text(encoding="utf-8")
    assert '# macos = ["open -a Terminal {path}"]' in written
    assert '# windows = ["wt -d {path}"]' in written
    assert 'linux = ["konsole --working-directory {path}"]' in written
    assert "[[actions.custom]]" in written
    assert 'name = "Open lazygit"' in written
    assert 'command = ["lazygit"]' in written
    assert 'mode = "terminal"' in written
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
    assert "max_output_kib = 512" in written
    assert "timeout_seconds = 120" in written


def test_config_save_service_preserves_advanced_and_unknown_settings(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """# Keep this comment.

[display]
show_hidden_files = false
theme = "textual-dark"
preview_syntax_theme = "monokai"
preview_max_kib = 1024
custom_preview_option = "keep"

[behavior]
confirm_delete = true
confirm_exit = false

[custom_plugin]
enabled = true
""",
        encoding="utf-8",
    )

    saved_path = LiveConfigSaveService().save(
        path=str(config_path),
        config=AppConfig(
            display=DisplayConfig(
                show_hidden_files=True,
                theme="tokyo-night",
                preview_syntax_theme="one-dark",
            ),
            behavior=BehaviorConfig(confirm_delete=False),
        ),
        preserve_unmanaged=True,
    )

    written = config_path.read_text(encoding="utf-8")
    assert saved_path == str(config_path)
    assert "# Keep this comment." in written
    assert "show_hidden_files = true" in written
    assert 'theme = "tokyo-night"' in written
    assert 'preview_syntax_theme = "one-dark"' in written
    assert "preview_max_kib = 1024" in written
    assert 'custom_preview_option = "keep"' in written
    assert "confirm_delete = false" in written
    assert "confirm_exit = false" in written
    assert "[custom_plugin]" in written
    assert "enabled = true" in written

    reloaded = AppConfigLoader(config_path_resolver=lambda: config_path).load()

    assert reloaded.config.display.preview_syntax_theme == "one-dark"
    assert reloaded.config.display.preview_max_kib == 1024
    assert reloaded.config.behavior.confirm_exit is False


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
    )
    config_path.write_text(render_app_config(config), encoding="utf-8")

    result = AppConfigLoader(config_path_resolver=lambda: config_path).load()

    assert result.warnings == ()
    assert result.config == config


def test_loader_ignores_legacy_help_bar_section_and_save_removes_it(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "[help_bar]\nbrowsing = [\"outdated help\"]\n",
        encoding="utf-8",
    )

    result = AppConfigLoader(config_path_resolver=lambda: config_path).load()

    assert result.config == AppConfig()
    assert result.warnings == ("[help_bar] is no longer supported and has been ignored.",)
    assert "[help_bar]" not in render_app_config(result.config)


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


def test_grep_search_config_default_is_unlimited() -> None:
    """grep_search.max_results のデフォルト値が None であることを確認."""
    config = AppConfig()
    assert config.grep_search.max_results is None


def test_loader_reads_grep_search_max_results(tmp_path) -> None:
    """config.toml から grep_search.max_results を読み込めることを確認."""
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
        [grep_search]
        max_results = 500
        """,
        encoding="utf-8",
    )

    result = AppConfigLoader(config_path_resolver=lambda: config_path).load()

    assert result.warnings == ()
    assert result.config.grep_search.max_results == 500


def test_render_app_config_includes_grep_search_section() -> None:
    """render_app_config が grep_search セクションを出力することを確認."""
    config = AppConfig(grep_search=GrepSearchConfig(max_results=1000))
    rendered = render_app_config(config)

    assert "[grep_search]" in rendered
    assert "max_results = 1000" in rendered


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
