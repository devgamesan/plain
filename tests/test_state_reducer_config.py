"""Test State Reducer Config tests."""
from tests.support.paths import TEST_HOME, TEST_PROJECT_ROOT
from tests.support.reducer import (
    AddBookmark,
    AppConfig,
    BeginFilterInput,
    BookmarkConfig,
    ConfigEditorState,
    ConfigLoadResult,
    ConfigReloadCompleted,
    ConfigReloadFailed,
    ConfigSaveCompleted,
    ConfigSaveFailed,
    CycleConfigEditorValue,
    DismissConfigEditor,
    ExternalLaunchCompleted,
    ExternalLaunchRequest,
    GuiEditorConfig,
    LoadChildPaneSnapshotEffect,
    MoveConfigEditorCursor,
    NotificationState,
    OpenPathInEditor,
    PaneState,
    RemoveBookmark,
    RunConfigReloadEffect,
    RunConfigSaveEffect,
    RunDirectorySizeEffect,
    SaveConfigEditor,
    _reduce_state,
    build_initial_app_state,
    reduce_app_state,
    replace,
)


def test_begin_filter_input_switches_mode_without_mutating_query() -> None:
    state = build_initial_app_state()

    next_state = _reduce_state(state, BeginFilterInput())

    assert next_state.ui_mode == "FILTER"
    assert next_state.filter == state.filter

def test_move_config_editor_cursor_clamps_to_visible_settings() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=build_initial_app_state().config,
        ),
    )

    next_state = _reduce_state(state, MoveConfigEditorCursor(delta=99))

    assert next_state.config_editor is not None
    assert next_state.config_editor.cursor_index == 12

def test_move_config_editor_cursor_reaches_preview_syntax_theme() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=build_initial_app_state().config,
            cursor_index=3,
        ),
    )

    next_state = _reduce_state(state, MoveConfigEditorCursor(delta=1))

    assert next_state.config_editor is not None
    assert next_state.config_editor.cursor_index == 4

def test_cycle_config_editor_editor_command_updates_draft_and_dirty_state() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=build_initial_app_state().config,
            cursor_index=0,
        ),
    )

    next_state = _reduce_state(state, CycleConfigEditorValue(delta=1))

    assert next_state.config_editor is not None
    assert next_state.config_editor.draft.editor.command == "nvim"
    assert next_state.config_editor.dirty is True

def test_cycle_config_editor_gui_editor_updates_draft_and_dirty_state() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=build_initial_app_state().config,
            cursor_index=1,
        ),
    )

    next_state = _reduce_state(state, CycleConfigEditorValue(delta=1))

    assert next_state.config_editor is not None
    assert next_state.config_editor.draft.gui_editor == GuiEditorConfig(
        command="codium --goto {path}:{line}:{column}",
        fallback_command="codium {path}",
    )
    assert next_state.config_editor.dirty is True

def test_cycle_config_editor_gui_editor_custom_value_moves_to_first_preset() -> None:
    base_state = build_initial_app_state(config_path="/tmp/zivo/config.toml")
    custom_config = replace(
        base_state.config,
        gui_editor=GuiEditorConfig(
            command="my-editor --line {line} {path}",
            fallback_command="my-editor {path}",
        ),
    )
    state = replace(
        base_state,
        config=custom_config,
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=custom_config,
            cursor_index=1,
        ),
    )

    next_state = _reduce_state(state, CycleConfigEditorValue(delta=1))

    assert next_state.config_editor is not None
    assert next_state.config_editor.draft.gui_editor == GuiEditorConfig()
    assert next_state.config_editor.dirty is True

def test_cycle_config_editor_value_updates_draft_and_dirty_state() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=build_initial_app_state().config,
            cursor_index=2,
        ),
    )

    next_state = _reduce_state(state, CycleConfigEditorValue(delta=1))

    assert next_state.config_editor is not None
    assert next_state.config_editor.draft.display.show_hidden_files is True
    assert next_state.config_editor.dirty is True

def test_cycle_config_editor_theme_updates_draft_and_dirty_state() -> None:
    original_state = build_initial_app_state(config_path="/tmp/zivo/config.toml")
    state = replace(
        original_state,
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=original_state.config,
            cursor_index=3,
        ),
    )

    next_state = _reduce_state(state, CycleConfigEditorValue(delta=1))

    assert next_state.config_editor is not None
    assert next_state.config_editor.draft.display.theme == "textual-light"
    assert next_state.config.display.theme == "textual-dark"
    assert next_state.config_editor.dirty is True

def test_cycle_config_editor_theme_supports_all_builtin_themes() -> None:
    base_state = build_initial_app_state()
    themed_config = replace(
        base_state.config,
        display=replace(base_state.config.display, theme="solarized-light"),
    )
    state = replace(
        base_state,
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=themed_config,
            cursor_index=3,
        ),
    )

    next_state = _reduce_state(state, CycleConfigEditorValue(delta=1))

    assert next_state.config_editor is not None
    assert next_state.config_editor.draft.display.theme == "textual-ansi"
    assert next_state.config_editor.dirty is True

def test_cycle_config_editor_text_preview_updates_draft_and_dirty_state() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=build_initial_app_state().config,
            cursor_index=5,
        ),
    )

    next_state = _reduce_state(state, CycleConfigEditorValue(delta=1))

    assert next_state.config_editor is not None
    assert next_state.config_editor.draft.display.enable_text_preview is False
    assert next_state.config_editor.dirty is True

def test_cycle_config_editor_image_preview_updates_draft_and_dirty_state() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=build_initial_app_state().config,
            cursor_index=6,
        ),
    )

    next_state = _reduce_state(state, CycleConfigEditorValue(delta=1))

    assert next_state.config_editor is not None
    assert next_state.config_editor.draft.display.enable_image_preview is False
    assert next_state.config_editor.dirty is True

def test_cycle_config_editor_pdf_preview_updates_draft_and_dirty_state() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=build_initial_app_state().config,
            cursor_index=7,
        ),
    )

    next_state = _reduce_state(state, CycleConfigEditorValue(delta=1))

    assert next_state.config_editor is not None
    assert next_state.config_editor.draft.display.enable_pdf_preview is False
    assert next_state.config_editor.dirty is True

def test_cycle_config_editor_office_preview_updates_draft_and_dirty_state() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=build_initial_app_state().config,
            cursor_index=8,
        ),
    )

    next_state = _reduce_state(state, CycleConfigEditorValue(delta=1))

    assert next_state.config_editor is not None
    assert next_state.config_editor.draft.display.enable_office_preview is False
    assert next_state.config_editor.dirty is True

def test_cycle_config_editor_preview_syntax_theme_updates_draft_and_dirty_state() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=build_initial_app_state().config,
            cursor_index=4,
        ),
    )

    next_state = _reduce_state(state, CycleConfigEditorValue(delta=1))

    assert next_state.config_editor is not None
    assert next_state.config_editor.draft.display.preview_syntax_theme == "abap"
    assert next_state.config_editor.dirty is True

def test_save_config_editor_emits_config_save_effect() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=replace(
                build_initial_app_state().config,
                behavior=replace(build_initial_app_state().config.behavior, confirm_delete=False),
            ),
            dirty=True,
        ),
    )

    result = reduce_app_state(state, SaveConfigEditor())

    assert result.state.pending_config_save_request_id == 1
    assert result.state.next_request_id == 2
    assert result.effects == (
        RunConfigSaveEffect(
            request_id=1,
            path="/tmp/zivo/config.toml",
            config=result.state.config_editor.draft,
            preserve_unmanaged=True,
        ),
    )

def test_add_bookmark_emits_config_save_effect() -> None:
    state = build_initial_app_state(config_path="/tmp/zivo/config.toml")

    result = reduce_app_state(state, AddBookmark(path=TEST_PROJECT_ROOT))

    assert result.state.pending_config_save_request_id == 1
    assert result.effects == (
        RunConfigSaveEffect(
            request_id=1,
            path="/tmp/zivo/config.toml",
            config=AppConfig(
                bookmarks=BookmarkConfig(paths=(TEST_PROJECT_ROOT,))
            ),
        ),
    )

def test_add_bookmark_ignores_duplicate_path() -> None:
    state = build_initial_app_state(
        config=AppConfig(bookmarks=BookmarkConfig(paths=(TEST_PROJECT_ROOT,)))
    )

    next_state = _reduce_state(state, AddBookmark(path=TEST_PROJECT_ROOT))

    assert next_state.notification == NotificationState(
        level="info",
        message="Directory is already bookmarked",
    )

def test_remove_bookmark_emits_config_save_effect() -> None:
    state = build_initial_app_state(
        config_path="/tmp/zivo/config.toml",
        config=AppConfig(
            bookmarks=BookmarkConfig(
                paths=(TEST_PROJECT_ROOT, TEST_HOME + '/src')
            )
        ),
    )

    result = reduce_app_state(state, RemoveBookmark(path=TEST_PROJECT_ROOT))

    assert result.state.pending_config_save_request_id == 1
    assert result.effects == (
        RunConfigSaveEffect(
            request_id=1,
            path="/tmp/zivo/config.toml",
            config=AppConfig(
                bookmarks=BookmarkConfig(paths=(TEST_HOME + '/src',))
            ),
        ),
    )

def test_config_save_completed_updates_runtime_state_and_clears_dirty_flag() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=replace(
                build_initial_app_state().config,
                behavior=replace(build_initial_app_state().config.behavior, confirm_delete=False),
            ),
            dirty=True,
        ),
        pending_config_save_request_id=3,
    )

    saved_config = state.config_editor.draft
    next_state = _reduce_state(
        state,
        ConfigSaveCompleted(
            request_id=3,
            path="/tmp/zivo/config.toml",
            config=saved_config,
        ),
    )

    assert next_state.pending_config_save_request_id is None
    assert next_state.config == saved_config
    assert next_state.confirm_delete is False
    assert next_state.config_editor is not None
    assert next_state.config_editor.dirty is False

def test_config_save_completed_clears_preview_when_disabled() -> None:
    path = TEST_PROJECT_ROOT + '/README.md'
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        ui_mode="CONFIG",
        current_pane=replace(
            build_initial_app_state().current_pane,
            cursor_path=path,
        ),
        child_pane=PaneState(
            directory_path=TEST_PROJECT_ROOT,
            entries=(),
            mode="preview",
            preview_path=path,
            preview_content="# Preview\n",
        ),
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=replace(
                build_initial_app_state().config,
                display=replace(
                    build_initial_app_state().config.display,
                    enable_text_preview=False,
                ),
            ),
            dirty=True,
        ),
        pending_config_save_request_id=3,
    )

    saved_config = state.config_editor.draft
    next_state = _reduce_state(
        state,
        ConfigSaveCompleted(
            request_id=3,
            path="/tmp/zivo/config.toml",
            config=saved_config,
        ),
    )

    assert next_state.config.display.enable_text_preview is False
    assert next_state.child_pane == PaneState(
        directory_path=TEST_PROJECT_ROOT,
        entries=(),
    )
    assert next_state.pending_child_pane_request_id is None

def test_config_save_completed_requests_preview_when_enabled() -> None:
    path = TEST_PROJECT_ROOT + '/README.md'
    base_state = build_initial_app_state(config_path="/tmp/zivo/config.toml")
    state = replace(
        base_state,
        ui_mode="CONFIG",
        config=replace(
            base_state.config,
            display=replace(base_state.config.display, enable_text_preview=False),
        ),
        current_pane=replace(base_state.current_pane, cursor_path=path),
        child_pane=PaneState(directory_path=TEST_PROJECT_ROOT, entries=()),
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=replace(
                base_state.config,
                display=replace(base_state.config.display, enable_text_preview=True),
            ),
            dirty=True,
        ),
        pending_config_save_request_id=3,
    )

    saved_config = state.config_editor.draft
    result = reduce_app_state(
        state,
        ConfigSaveCompleted(
            request_id=3,
            path="/tmp/zivo/config.toml",
            config=saved_config,
        ),
    )

    assert result.state.config.display.enable_text_preview is True
    assert result.state.pending_child_pane_request_id == 1
    assert result.effects == (
        LoadChildPaneSnapshotEffect(
            request_id=1,
            current_path=TEST_PROJECT_ROOT,
            cursor_path=path,
        ),
        RunDirectorySizeEffect(
            request_id=2,
            paths=(
                TEST_PROJECT_ROOT + '/docs',
                TEST_PROJECT_ROOT + '/src',
                TEST_PROJECT_ROOT + '/tests',
            ),
        ),
    )

def test_config_save_failed_sets_error_notification() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        pending_config_save_request_id=4,
    )

    next_state = _reduce_state(state, ConfigSaveFailed(request_id=4, message="disk full"))

    assert next_state.pending_config_save_request_id is None
    assert next_state.notification == NotificationState(
        level="error",
        message="Failed to save config: disk full",
    )

def test_config_editor_blocks_raw_edit_when_changes_are_pending() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=replace(
                build_initial_app_state().config,
                display=replace(build_initial_app_state().config.display, theme="dracula"),
            ),
            dirty=True,
        ),
    )

    result = reduce_app_state(state, OpenPathInEditor("/tmp/zivo/config.toml"))

    assert result.effects == ()
    assert result.state.notification == NotificationState(
        level="warning",
        message="Save or close pending Config Editor changes before editing config.toml",
    )

def test_config_editor_raw_edit_requests_reload_after_editor_exits() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=build_initial_app_state().config,
        ),
    )

    result = reduce_app_state(
        state,
        ExternalLaunchCompleted(
            request_id=1,
            request=ExternalLaunchRequest(
                kind="open_editor",
                path="/tmp/zivo/config.toml",
                reload_config_after_exit=True,
            ),
        ),
    )

    assert result.state.pending_config_reload_request_id == 1
    assert result.state.next_request_id == 2
    assert result.effects == (
        RunConfigReloadEffect(request_id=1, path="/tmp/zivo/config.toml"),
    )

def test_config_reload_completed_updates_runtime_and_editor_draft() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=build_initial_app_state().config,
            dirty=True,
        ),
        pending_config_reload_request_id=4,
    )
    loaded_config = replace(
        state.config,
        display=replace(state.config.display, theme="dracula"),
    )

    result = reduce_app_state(
        state,
        ConfigReloadCompleted(
            request_id=4,
            result=ConfigLoadResult(
                config=loaded_config,
                path="/tmp/zivo/config.toml",
            ),
        ),
    )

    assert result.state.config.display.theme == "dracula"
    assert result.state.config_editor is not None
    assert result.state.config_editor.draft == loaded_config
    assert result.state.config_editor.dirty is False
    assert result.state.pending_config_reload_request_id is None

def test_config_reload_fatal_result_keeps_current_runtime_config() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        pending_config_reload_request_id=4,
    )
    result = reduce_app_state(
        state,
        ConfigReloadCompleted(
            request_id=4,
            result=ConfigLoadResult(
                config=AppConfig(),
                path="/tmp/zivo/config.toml",
                warnings=("Failed to parse config.toml: bad value",),
                fatal=True,
            ),
        ),
    )

    assert result.state.config == state.config
    assert result.state.pending_config_reload_request_id is None
    assert result.state.notification == NotificationState(
        level="error",
        message="Failed to parse config.toml: bad value",
    )

def test_config_reload_failed_sets_error_notification() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        pending_config_reload_request_id=4,
    )

    result = reduce_app_state(
        state,
        ConfigReloadFailed(request_id=4, message="permission denied"),
    )

    assert result.state.notification == NotificationState(
        level="error",
        message="Failed to reload config.toml: permission denied",
    )

def test_dismiss_config_editor_returns_to_browsing() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=build_initial_app_state().config,
        ),
    )

    next_state = _reduce_state(state, DismissConfigEditor())

    assert next_state.ui_mode == "BROWSING"
    assert next_state.config_editor is None
