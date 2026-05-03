# ruff: noqa: F403,F405

from .input_dispatch_helpers import *


def test_filter_q_updates_query_instead_of_exiting() -> None:
    state = build_initial_app_state()
    state = replace(
        state,
        ui_mode="FILTER",
    )

    actions = dispatch_key_input(state, key="q", character="q")

    assert actions == (SetNotification(None), SetFilterQuery("q", active=True))


def test_filter_bound_space_without_character_is_rejected() -> None:
    state = replace(build_initial_app_state(), ui_mode="FILTER")

    actions = dispatch_key_input(state, key="space")

    assert actions == (
        SetNotification(
            NotificationState(
                level="warning",
                message="This key is unavailable while editing the filter",
            )
        ),
    )


def test_filter_character_dispatches_query_update() -> None:
    state = build_initial_app_state()
    state = replace(state, ui_mode="FILTER")

    actions = dispatch_key_input(state, key="r", character="r")

    assert actions == (SetNotification(None), SetFilterQuery("r", active=True))


def test_filter_backspace_updates_query() -> None:
    state = build_initial_app_state()
    state = replace(
        state,
        ui_mode="FILTER",
        filter=replace(state.filter, query="rea", active=True),
    )

    actions = dispatch_key_input(state, key="backspace")

    assert actions == (SetNotification(None), SetFilterQuery("re", active=True))


def test_filter_space_is_unavailable() -> None:
    state = build_initial_app_state()
    state = replace(state, ui_mode="FILTER")

    actions = dispatch_key_input(state, key="space")

    assert actions == (
        SetNotification(
            NotificationState(
                level="warning",
                message="This key is unavailable while editing the filter",
            )
        ),
    )


def test_filter_enter_confirms_filter() -> None:
    state = build_initial_app_state()
    state = replace(state, ui_mode="FILTER")

    actions = dispatch_key_input(state, key="enter")

    assert actions == (SetNotification(None), ConfirmFilterInput())


def test_filter_down_confirms_filter() -> None:
    state = build_initial_app_state()
    state = replace(state, ui_mode="FILTER")

    actions = dispatch_key_input(state, key="down")

    assert actions == (SetNotification(None), ConfirmFilterInput())


def test_filter_escape_cancels_filter() -> None:
    state = build_initial_app_state()
    state = replace(state, ui_mode="FILTER")

    actions = dispatch_key_input(state, key="escape")

    assert actions == (SetNotification(None), CancelFilterInput())


def test_confirm_escape_returns_to_browsing() -> None:
    state = build_initial_app_state()
    state = replace(state, ui_mode="CONFIRM")

    actions = dispatch_key_input(state, key="escape")

    assert actions == (SetNotification(None), CancelPasteConflict())


def test_name_conflict_confirm_enter_returns_to_input() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="CONFIRM",
        name_conflict=NameConflictState(kind="rename", name="docs"),
    )

    actions = dispatch_key_input(state, key="enter")

    assert actions == (SetNotification(None), DismissNameConflict())


def test_name_conflict_confirm_escape_returns_to_input() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="CONFIRM",
        name_conflict=NameConflictState(kind="create_file", name="docs"),
    )

    actions = dispatch_key_input(state, key="escape")

    assert actions == (SetNotification(None), DismissNameConflict())


def test_detail_enter_closes_attribute_dialog() -> None:
    state = replace(build_initial_app_state(), ui_mode="DETAIL")

    actions = dispatch_key_input(state, key="enter")

    assert actions == (SetNotification(None), DismissAttributeDialog())


def test_config_down_moves_cursor() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=build_initial_app_state().config,
        ),
    )

    actions = dispatch_key_input(state, key="down")

    assert actions == (SetNotification(None), MoveConfigEditorCursor(delta=1))


def test_config_ctrl_n_moves_cursor() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=build_initial_app_state().config,
        ),
    )

    actions = dispatch_key_input(state, key="ctrl+j")

    assert actions == (SetNotification(None), MoveConfigEditorCursor(delta=1))


def test_config_ctrl_k_moves_cursor() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=build_initial_app_state().config,
        ),
    )

    actions = dispatch_key_input(state, key="ctrl+k")

    assert actions == (SetNotification(None), MoveConfigEditorCursor(delta=-1))


def test_config_enter_cycles_selected_value() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=build_initial_app_state().config,
        ),
    )

    actions = dispatch_key_input(state, key="enter")

    assert actions == (SetNotification(None), CycleConfigEditorValue(delta=1))


def test_config_s_saves_editor() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=build_initial_app_state().config,
        ),
    )

    actions = dispatch_key_input(state, key="s", character="s")

    assert actions == (SetNotification(None), SaveConfigEditor())


def test_config_e_opens_config_file_in_editor() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=build_initial_app_state().config,
        ),
    )

    actions = dispatch_key_input(state, key="e", character="e")

    assert actions == (SetNotification(None), OpenPathInEditor("/tmp/zivo/config.toml"))


def test_config_escape_closes_editor() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=build_initial_app_state().config,
        ),
    )

    actions = dispatch_key_input(state, key="escape")

    assert actions == (SetNotification(None), DismissConfigEditor())


def test_config_unbound_key_shows_guidance() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=build_initial_app_state().config,
        ),
    )

    actions = dispatch_key_input(state, key="x", character="x")

    assert actions == (
        SetNotification(
            NotificationState(
                level="warning",
                message=(
                        "Use ↑↓ or Ctrl+j/k to choose, ←→ or Enter to change, "
                    "s to save, e to edit the file, r to reset help, or Esc to close"
                ),
            )
        ),
    )


def test_confirm_o_selects_overwrite_resolution() -> None:
    state = replace(build_initial_app_state(), ui_mode="CONFIRM")

    actions = dispatch_key_input(state, key="o", character="o")

    assert actions == (SetNotification(None), ResolvePasteConflict("overwrite"))


def test_delete_confirm_enter_dispatches_confirmation() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="CONFIRM",
        delete_confirmation=DeleteConfirmationState(
            paths=(
                "/home/tadashi/develop/zivo/docs",
                "/home/tadashi/develop/zivo/src",
            )
        ),
    )

    actions = dispatch_key_input(state, key="enter")

    assert actions == (SetNotification(None), ConfirmDeleteTargets())


def test_delete_confirm_escape_cancels_confirmation() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="CONFIRM",
        delete_confirmation=DeleteConfirmationState(
            paths=("/home/tadashi/develop/zivo/docs",),
        ),
    )

    actions = dispatch_key_input(state, key="escape")

    assert actions == (SetNotification(None), CancelDeleteConfirmation())


def test_zip_compress_confirm_enter_dispatches_confirmation() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="CONFIRM",
        zip_compress_confirmation=ZipCompressConfirmationState(
            request=CreateZipArchiveRequest(
                source_paths=("/home/tadashi/develop/zivo/docs",),
                destination_path="/home/tadashi/develop/zivo/docs.zip",
                root_dir="/home/tadashi/develop/zivo",
            ),
            total_entries=3,
        ),
    )

    actions = dispatch_key_input(state, key="enter")

    assert actions == (SetNotification(None), ConfirmZipCompress())


def test_zip_compress_confirm_escape_cancels_confirmation() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="CONFIRM",
        zip_compress_confirmation=ZipCompressConfirmationState(
            request=CreateZipArchiveRequest(
                source_paths=("/home/tadashi/develop/zivo/docs",),
                destination_path="/home/tadashi/develop/zivo/docs.zip",
                root_dir="/home/tadashi/develop/zivo",
            ),
            total_entries=3,
        ),
    )

    actions = dispatch_key_input(state, key="escape")

    assert actions == (SetNotification(None), CancelZipCompressConfirmation())


def test_rename_character_dispatches_input_update() -> None:
    state = build_initial_app_state()
    state = replace(
        state,
        ui_mode="RENAME",
        pending_input=PendingInputState(prompt="Rename: ", value="doc", cursor_pos=3),
    )

    actions = dispatch_key_input(state, key="s", character="s")

    assert actions == (SetNotification(None), SetPendingInputValue("docs", cursor_pos=4))


def test_create_space_dispatches_input_update() -> None:
    state = build_initial_app_state()
    state = replace(
        state,
        ui_mode="CREATE",
        pending_input=PendingInputState(
            prompt="New file: ", value="new", cursor_pos=3, create_kind="file"
        ),
    )

    actions = dispatch_key_input(state, key="space", character=" ")

    assert actions == (SetNotification(None), SetPendingInputValue("new ", cursor_pos=4))


def test_zip_enter_dispatches_submit_pending_input() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="ZIP",
        pending_input=PendingInputState(
            prompt="Compress to: ",
            value="/tmp/output.zip",
            zip_source_paths=("/home/tadashi/develop/zivo/docs",),
        ),
    )

    actions = dispatch_key_input(state, key="enter")

    assert actions == (SetNotification(None), SubmitPendingInput())


def test_zip_printable_character_dispatches_input_update() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="ZIP",
        pending_input=PendingInputState(
            prompt="Compress to: ",
            value="/tmp/output",
            cursor_pos=11,
            zip_source_paths=("/home/tadashi/develop/zivo/docs",),
        ),
    )

    actions = dispatch_key_input(state, key="z", character="z")

    assert actions == (SetNotification(None), SetPendingInputValue("/tmp/outputz", cursor_pos=12))


def test_pending_input_backspace_updates_value() -> None:
    state = build_initial_app_state()
    state = replace(
        state,
        ui_mode="RENAME",
        pending_input=PendingInputState(prompt="Rename: ", value="docs", cursor_pos=4),
    )

    actions = dispatch_key_input(state, key="backspace")

    assert actions == (SetNotification(None), SetPendingInputValue("doc", cursor_pos=3))


def test_pending_input_enter_submits() -> None:
    state = replace(build_initial_app_state(), ui_mode="RENAME")

    actions = dispatch_key_input(state, key="enter")

    assert actions == (SetNotification(None), SubmitPendingInput())


def test_pending_input_escape_cancels() -> None:
    state = replace(build_initial_app_state(), ui_mode="RENAME")

    actions = dispatch_key_input(state, key="escape")

    assert actions == (SetNotification(None), CancelPendingInput())


def test_pending_input_unbound_key_shows_guidance() -> None:
    state = build_initial_app_state()
    state = replace(
        state,
        ui_mode="RENAME",
        pending_input=PendingInputState(prompt="Rename: ", value="docs", cursor_pos=4),
    )

    actions = dispatch_key_input(state, key="left")

    assert actions == (SetNotification(None), MovePendingInputCursor(delta=-1))


def test_symlink_tab_completes_pending_input_path(tmp_path) -> None:
    (tmp_path / "docs").mkdir()
    state = replace(
        build_initial_app_state(),
        current_path=str(tmp_path),
        current_pane=replace(build_initial_app_state().current_pane, directory_path=str(tmp_path)),
        ui_mode="SYMLINK",
        pending_input=PendingInputState(
            prompt="Create link at: ",
            value="do",
            cursor_pos=2,
            symlink_source_path=str(tmp_path / "README.md"),
        ),
    )

    actions = dispatch_key_input(state, key="tab")

    assert actions == (
        SetNotification(None),
        SetPendingInputValue("docs/", cursor_pos=5),
    )


def test_busy_key_shows_warning_message() -> None:
    state = build_initial_app_state()
    state = replace(state, ui_mode="BUSY")

    actions = dispatch_key_input(state, key="x", character="x")

    assert actions == (
        SetNotification(
            NotificationState(level="warning", message="Input ignored while processing")
        ),
    )
