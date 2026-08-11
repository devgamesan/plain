# ruff: noqa: F403,F405

from .input_dispatch_helpers import *


def test_palette_enter_submits_selected_command() -> None:
    state = replace(build_initial_app_state(), ui_mode="PALETTE")

    actions = dispatch_key_input(state, key="enter")

    assert actions == (SetNotification(None), SubmitCommandPalette())


def test_palette_escape_closes_command_palette() -> None:
    state = replace(build_initial_app_state(), ui_mode="PALETTE")

    actions = dispatch_key_input(state, key="escape")

    assert actions == (SetNotification(None), CancelCommandPalette())


def test_palette_down_moves_cursor() -> None:
    state = replace(build_initial_app_state(), ui_mode="PALETTE")

    actions = dispatch_key_input(state, key="down")

    assert actions == (SetNotification(None), MoveCommandPaletteCursor(delta=1))


def test_palette_ctrl_e_opens_grep_result_in_editor() -> None:
    from zivo.state.models import CommandPaletteState
    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(
            source="grep_search",
            query="test",
        ),
    )

    actions = dispatch_key_input(state, key="ctrl+e")

    assert actions == (SetNotification(None), OpenGrepResultInEditor())


def test_palette_ctrl_e_opens_find_result_in_editor() -> None:
    from zivo.state.models import CommandPaletteState
    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(
            source="file_search",
            query="test",
        ),
    )

    actions = dispatch_key_input(state, key="ctrl+e")

    assert actions == (SetNotification(None), OpenFindResultInEditor())


def test_palette_ctrl_o_opens_grep_result_in_gui_editor() -> None:
    from zivo.state.models import CommandPaletteState
    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(
            source="grep_search",
            query="test",
        ),
    )

    actions = dispatch_key_input(state, key="ctrl+o")

    assert actions == (SetNotification(None), OpenGrepResultInGuiEditor())


def test_palette_ctrl_o_opens_find_result_in_gui_editor() -> None:
    from zivo.state.models import CommandPaletteState
    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(
            source="file_search",
            query="test",
        ),
    )

    actions = dispatch_key_input(state, key="ctrl+o")

    assert actions == (SetNotification(None), OpenFindResultInGuiEditor())


def test_palette_e_key_does_not_open_editor_for_other_sources() -> None:
    from zivo.state.models import CommandPaletteState
    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(
            source="commands",
            query="test",
        ),
    )

    actions = dispatch_key_input(state, key="e", character="e")

    # e キーは commands では OpenFindResultInEditor を生成せず、文字として扱われる
    assert actions == (SetNotification(None), SetCommandPaletteQuery("teste"))


def test_palette_ctrl_n_moves_cursor_down_in_grep_palette() -> None:
    from zivo.state.models import CommandPaletteState
    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(
            source="grep_search",
            query="test",
        ),
    )

    actions = dispatch_key_input(state, key="ctrl+j")

    assert actions == (SetNotification(None), MoveCommandPaletteCursor(delta=1))


def test_palette_ctrl_k_moves_cursor_up_in_grep_palette() -> None:
    from zivo.state.models import CommandPaletteState
    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(
            source="grep_search",
            query="test",
        ),
    )

    actions = dispatch_key_input(state, key="ctrl+k")

    assert actions == (SetNotification(None), MoveCommandPaletteCursor(delta=-1))


def test_palette_ctrl_j_moves_cursor_down_in_file_search_palette() -> None:
    from zivo.state.models import CommandPaletteState
    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(
            source="file_search",
            query="test",
        ),
    )

    actions = dispatch_key_input(state, key="ctrl+j")

    assert actions == (SetNotification(None), MoveCommandPaletteCursor(delta=1))


def test_palette_ctrl_k_moves_cursor_up_in_file_search_palette() -> None:
    from zivo.state.models import CommandPaletteState
    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(
            source="file_search",
            query="test",
        ),
    )

    actions = dispatch_key_input(state, key="ctrl+k")

    assert actions == (SetNotification(None), MoveCommandPaletteCursor(delta=-1))


def test_palette_ctrl_j_moves_cursor_down_in_replace_palette() -> None:
    from zivo.state.models import CommandPaletteState

    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(
            source="replace_text",
            replace_preview=ReplacePreviewPaletteState(
                find_text="todo",
            ),
        ),
    )

    actions = dispatch_key_input(state, key="ctrl+j")

    assert actions == (SetNotification(None), MoveCommandPaletteCursor(delta=1))


def test_palette_ctrl_k_moves_cursor_up_in_replace_palette() -> None:
    from zivo.state.models import CommandPaletteState

    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(
            source="replace_text",
            replace_preview=ReplacePreviewPaletteState(
                find_text="todo",
            ),
        ),
    )

    actions = dispatch_key_input(state, key="ctrl+k")

    assert actions == (SetNotification(None), MoveCommandPaletteCursor(delta=-1))


def test_palette_printable_key_updates_query() -> None:
    state = replace(build_initial_app_state(), ui_mode="PALETTE")

    actions = dispatch_key_input(state, key="f", character="f")

    assert actions == (SetNotification(None), SetCommandPaletteQuery("f"))


def test_file_search_tab_cycles_through_extension_fields() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(source="file_search"),
    )

    actions = dispatch_key_input(state, key="tab")

    assert actions == (SetNotification(None), CycleFileSearchField(delta=1))


def test_file_search_printable_key_updates_include_field() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(
            source="file_search",
            file_search=FileSearchPaletteState(active_field="include"),
        ),
    )

    actions = dispatch_key_input(state, key="p", character="p")

    assert actions == (SetNotification(None), SetFileSearchField(field="include", value="p"))


def test_go_palette_j_and_k_are_query_input() -> None:
    from zivo.state.models import CommandPaletteState

    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(source="go", query="ab"),
    )

    assert dispatch_key_input(state, key="j", character="j") == (
        SetNotification(None),
        SetCommandPaletteQuery("abj"),
    )
    assert dispatch_key_input(state, key="k", character="k") == (
        SetNotification(None),
        SetCommandPaletteQuery("abk"),
    )


def test_palette_space_updates_query() -> None:
    state = replace(build_initial_app_state(), ui_mode="PALETTE")

    actions = dispatch_key_input(state, key="space", character=" ")

    assert actions == (SetNotification(None), SetCommandPaletteQuery(" "))


def test_palette_bound_space_without_character_updates_query() -> None:
    state = replace(build_initial_app_state(), ui_mode="PALETTE")

    actions = dispatch_key_input(state, key="space")

    assert actions == (SetNotification(None), SetCommandPaletteQuery(" "))


def test_palette_pageup_moves_cursor_by_page() -> None:
    state = replace(build_initial_app_state(), ui_mode="PALETTE")

    actions = dispatch_key_input(state, key="pageup")

    assert actions == (SetNotification(None), MoveCommandPaletteCursor(delta=-14))


def test_palette_pagedown_moves_cursor_by_page() -> None:
    state = replace(build_initial_app_state(), ui_mode="PALETTE")

    actions = dispatch_key_input(state, key="pagedown")

    assert actions == (SetNotification(None), MoveCommandPaletteCursor(delta=14))


def test_palette_unbound_key_shows_guidance() -> None:
    state = replace(build_initial_app_state(), ui_mode="PALETTE")

    actions = dispatch_key_input(state, key="delete")

    assert actions == (
        SetNotification(
            NotificationState(
                level="warning",
                message="Use arrows, type to filter, Enter to run, or Esc to cancel",
            )
        ),
    )


def test_palette_home_jumps_to_start() -> None:
    state = replace(build_initial_app_state(), ui_mode="PALETTE")

    actions = dispatch_key_input(state, key="home")

    assert actions == (SetNotification(None), MoveCommandPaletteCursor(delta=-999999))


def test_palette_end_jumps_to_end() -> None:
    state = replace(build_initial_app_state(), ui_mode="PALETTE")

    actions = dispatch_key_input(state, key="end")

    assert actions == (SetNotification(None), MoveCommandPaletteCursor(delta=999999))


def test_palette_tab_cycles_rff_fields() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(source="replace_in_found_files"),
    )

    actions = dispatch_key_input(state, key="tab")

    assert actions == (
        SetNotification(None),
        CycleFindReplaceField(delta=1),
    )


def test_palette_shift_tab_cycles_rff_fields_reverse() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(source="replace_in_found_files"),
    )

    actions = dispatch_key_input(state, key="shift+tab")

    assert actions == (
        SetNotification(None),
        CycleFindReplaceField(delta=-1),
    )


def test_palette_printable_key_updates_rff_filename_field() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(
            source="replace_in_found_files",
            rff=RffPaletteState(active_field="filename"),
        ),
    )

    actions = dispatch_key_input(state, key="r", character="r")

    assert actions == (
        SetNotification(None),
        SetFindReplaceField(field="filename", value="r"),
    )


def test_palette_printable_key_updates_rff_find_field() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(
            source="replace_in_found_files",
            rff=RffPaletteState(active_field="find"),
        ),
    )

    actions = dispatch_key_input(state, key="t", character="t")

    assert actions == (
        SetNotification(None),
        SetFindReplaceField(field="find", value="t"),
    )


def test_palette_backspace_updates_rff_field() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(
            source="replace_in_found_files",
            rff=RffPaletteState(active_field="find", find_text="todo"),
        ),
    )

    actions = dispatch_key_input(state, key="backspace")

    assert actions == (
        SetNotification(None),
        SetFindReplaceField(field="find", value="tod"),
    )


def test_palette_ctrl_x_saves_grep_results_when_grep_search_results() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(
            source="grep_search",
            grep_search=GrepSearchPaletteState(
                keyword="hello",
                results=(
                    GrepSearchResultState(
                        path="/root/src/main.py",
                        display_path="src/main.py",
                        line_number=10,
                        line_text="def hello():",
                    ),
                ),
            ),
        ),
    )

    actions = dispatch_key_input(state, key="ctrl+x")

    assert actions == (SetNotification(None), SaveGrepResults())


def test_palette_ctrl_x_dispatches_save_for_grep_source() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(
            source="grep_search",
            grep_search=GrepSearchPaletteState(keyword="hello"),
        ),
    )

    actions = dispatch_key_input(state, key="ctrl+x")

    assert actions == (SetNotification(None), SaveGrepResults())


def test_palette_ctrl_x_works_for_grep_search_source() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(
            source="grep_search",
            grep_search=GrepSearchPaletteState(
                keyword="test",
                results=(
                    GrepSearchResultState(
                        path="/root/src/test.py",
                        display_path="src/test.py",
                        line_number=5,
                        line_text="def test():",
                    ),
                ),
            ),
        ),
    )

    actions = dispatch_key_input(state, key="ctrl+x")

    assert actions == (SetNotification(None), SaveGrepResults())
