"""Selector tests for status, help, input, and dialog views."""
from tests.support.paths import TEST_PROJECT_ROOT
from tests.support.selectors import (
    S_IFREG,
    AppConfig,
    ArchiveExtractConfirmationState,
    AttributeInspectionState,
    BeginCreateInput,
    BeginFilterInput,
    CommandPaletteState,
    ConfigEditorState,
    ConfirmFilterInput,
    CreateZipArchiveRequest,
    DeleteConfirmationState,
    EditorConfig,
    ExtractArchiveRequest,
    NameConflictState,
    NotificationState,
    PasteConflict,
    PasteConflictState,
    PasteRequest,
    PendingInputState,
    PendingKeySequenceState,
    SetFilterQuery,
    SetNotification,
    ToggleTransferMode,
    ZipCompressConfirmationState,
    _reduce_state,
    build_initial_app_state,
    os,
    replace,
    select_attribute_dialog_state,
    select_config_dialog_state,
    select_conflict_dialog_state,
    select_help_bar_state,
    select_input_bar_state,
    select_input_dialog_state,
    select_status_bar_state,
)


def test_select_attribute_dialog_state_formats_selected_entry() -> None:
    state = replace(
        build_initial_app_state(),
        attribute_inspection=AttributeInspectionState(
            name="README.md",
            kind="file",
            path=TEST_PROJECT_ROOT + '/README.md',
            size_bytes=2_150,
            modified_at=build_initial_app_state().current_pane.entries[3].modified_at,
            hidden=False,
            permissions_mode=S_IFREG | 0o644,
        ),
    )

    dialog = select_attribute_dialog_state(state)

    assert dialog is not None
    assert dialog.title == "Attributes: README.md"
    assert "Name: README.md" in dialog.lines
    assert "Type: File" in dialog.lines
    assert "Symlink: No" in dialog.lines
    assert 'Path: ' + TEST_PROJECT_ROOT + '/README.md' in dialog.lines
    assert "Size: 2.1KiB" in dialog.lines
    assert "Hidden: No" in dialog.lines
    assert "Permissions: -rw-r--r-- (644)" in dialog.lines
    assert dialog.options == ("enter close", "esc close")

def test_select_config_dialog_state_formats_editor_lines() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=build_initial_app_state().config,
            cursor_index=3,
            dirty=True,
        ),
    )

    dialog = select_config_dialog_state(state)

    assert dialog is not None
    assert dialog.title == "Config Editor (Basic Settings)*"
    assert "Path: /tmp/zivo/config.toml" in dialog.lines
    assert "  ── Editors ──" in dialog.lines
    assert "  Editor command: system default" in dialog.lines
    assert "  GUI editor: VS Code" in dialog.lines
    assert "  ── Appearance ──" in dialog.lines
    assert "> Theme: textual-dark" in dialog.lines
    assert "  Text preview: true" in dialog.lines
    assert "  Image preview: true" in dialog.lines
    assert "  Preview syntax theme: auto" in dialog.lines
    assert "  ── Sorting ──" in dialog.lines
    assert "  Default sort field: name" in dialog.lines
    assert "  ── Selected Setting ──" in dialog.lines
    assert "  Theme" in dialog.lines
    assert "  Sets the application theme used by the panes, dialogs, and status UI." in dialog.lines
    assert "  Changing this here previews the theme immediately before saving." in dialog.lines
    assert "  Current behavior: `textual-dark`." in dialog.lines
    hint = "Editor presets: system default, nvim, vim, nano, hx, micro, emacs -nw, edit"
    assert hint in dialog.lines
    assert (
        "GUI editor presets: VS Code, VSCodium, Cursor, Sublime Text, Zed, "
        "JetBrains IDEA, PyCharm, WebStorm, Kate"
    ) in dialog.lines
    assert "  ── Advanced Settings ──" in dialog.lines
    assert "  Edit config.toml with e for advanced, custom, and future settings." in dialog.lines
    assert "  Saving here preserves settings that are not shown above." in dialog.lines
    assert dialog.options == (
        "↑↓/Ctrl+j/k choose",
        "←→/enter change",
        "s save",
        "e advanced config",
        "esc close",
    )

def test_select_config_dialog_state_shows_custom_editor_command_hint() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=AppConfig(editor=EditorConfig(command="nvim -u NONE")),
        ),
    )

    dialog = select_config_dialog_state(state)

    assert dialog is not None
    assert "> Editor command: custom (raw config only)" in dialog.lines
    assert "Custom editor command: nvim -u NONE" in dialog.lines
    assert (
        "  Current behavior: custom raw command `nvim -u NONE` is preserved."
        in dialog.lines
    )
    assert "  Custom commands can only be edited in the raw config file with `e`." in dialog.lines

def test_select_conflict_dialog_state_formats_create_directory_conflict() -> None:
    state = replace(
        build_initial_app_state(),
        name_conflict=NameConflictState(kind="create_dir", name="docs"),
    )

    dialog = select_conflict_dialog_state(state)

    assert dialog is not None
    assert dialog.title == "Create Directory Conflict"
    assert "creating the directory" in dialog.message

def test_select_conflict_dialog_state_formats_delete_confirmation() -> None:
    state = replace(
        build_initial_app_state(),
        delete_confirmation=DeleteConfirmationState(
            paths=(
                TEST_PROJECT_ROOT + '/docs',
                TEST_PROJECT_ROOT + '/src',
            )
        ),
    )

    dialog = select_conflict_dialog_state(state)

    assert dialog is not None
    assert dialog.title == "Move to Trash Confirmation"
    assert dialog.message == "Move 2 items to Trash? The first target is docs."
    assert dialog.options == ("enter move to trash", "esc cancel")

def test_select_conflict_dialog_state_formats_extract_confirmation() -> None:
    state = replace(
        build_initial_app_state(),
        archive_extract_confirmation=ArchiveExtractConfirmationState(
            request=ExtractArchiveRequest(
                source_path=TEST_PROJECT_ROOT + '/archive.zip',
                destination_path="/tmp/output/archive",
            ),
            conflict_count=2,
            first_conflict_path="/tmp/output/archive/notes.txt",
            total_entries=5,
        ),
    )

    dialog = select_conflict_dialog_state(state)

    assert dialog is not None
    assert dialog.title == "Extract Archive Confirmation"
    assert "2 archive path(s) already exist" in dialog.message
    assert dialog.options == ("enter continue", "esc return to input")

def test_select_conflict_dialog_state_formats_first_conflict() -> None:
    conflict = PasteConflict(
        source_path=TEST_PROJECT_ROOT + '/docs',
        destination_path=TEST_PROJECT_ROOT + '/docs',
    )
    state = replace(
        build_initial_app_state(),
        paste_conflict=PasteConflictState(
            request=PasteRequest(
                mode="copy",
                source_paths=(TEST_PROJECT_ROOT + '/docs',),
                destination_dir=TEST_PROJECT_ROOT,
            ),
            conflicts=(conflict,),
            first_conflict=conflict,
        ),
    )

    dialog = select_conflict_dialog_state(state)

    assert dialog is not None
    assert dialog.title == "Paste Conflict"
    assert "o overwrite" in dialog.options

def test_select_conflict_dialog_state_formats_permanent_delete_confirmation() -> None:
    state = replace(
        build_initial_app_state(),
        delete_confirmation=DeleteConfirmationState(
            paths=(TEST_PROJECT_ROOT + '/docs',),
            mode="permanent",
            total_size_bytes=2048,
        ),
    )

    dialog = select_conflict_dialog_state(state)

    assert dialog is not None
    assert dialog.title == "Permanently Delete Confirmation"
    assert dialog.message.startswith("Permanently delete 1 item? This cannot be undone.")
    assert "This cannot be undone" in dialog.message
    assert "2.0KiB" in dialog.message
    assert "docs" in dialog.message
    assert dialog.options == ("enter permanently delete", "esc cancel")

def test_select_conflict_dialog_state_formats_rename_conflict() -> None:
    state = replace(
        build_initial_app_state(),
        name_conflict=NameConflictState(kind="rename", name="src"),
    )

    dialog = select_conflict_dialog_state(state)

    assert dialog is not None
    assert dialog.title == "Rename Conflict"
    assert dialog.options == ("enter return to input", "esc return to input")

def test_select_conflict_dialog_state_formats_zip_confirmation() -> None:
    state = replace(
        build_initial_app_state(),
        zip_compress_confirmation=ZipCompressConfirmationState(
            request=CreateZipArchiveRequest(
                source_paths=(TEST_PROJECT_ROOT + '/docs',),
                destination_path=TEST_PROJECT_ROOT + '/docs.zip',
                root_dir=TEST_PROJECT_ROOT,
            ),
            total_entries=4,
        ),
    )

    dialog = select_conflict_dialog_state(state)

    assert dialog is not None
    assert dialog.title == "Zip Compression Confirmation"
    assert "docs.zip already exists" in dialog.message
    assert dialog.options == ("enter overwrite", "esc return to input")

def test_select_help_bar_defaults_to_browsing_shortcuts() -> None:
    state = build_initial_app_state()

    help_state = select_help_bar_state(state)
    split_terminal_hint = " | t term" if os.name == "posix" else ""

    assert help_state.lines == (
        "enter open | e edit | / filter | s sort | . hidden | [ ] bk/fwd | q quit",
        "space select | c copy | x cut | v paste | d trash | r rename | z undo",
        f"f find | g grep | G go | n new-file | N new-dir{split_terminal_hint} | : palette",
    )
    assert help_state.text == (
        "enter open | e edit | / filter | s sort | . hidden | [ ] bk/fwd | q quit\n"
        "space select | c copy | x cut | v paste | d trash | r rename | z undo\n"
            f"f find | g grep | G go | n new-file | N new-dir{split_terminal_hint} | : palette"
    )

def test_select_help_bar_for_transfer_mode_prioritizes_transfer_actions() -> None:
    state = _reduce_state(build_initial_app_state(), ToggleTransferMode())

    help_state = select_help_bar_state(state)

    assert help_state.lines == (
        "enter dir | . hidden | Tab switch-pane | p/Esc close | q quit",
        "space select | c copy-to-pane | m move-to-pane | d trash | r rename | z undo",
        "n new-file | N new-dir | G go | : palette",
    )
    assert help_state.text == (
        "enter dir | . hidden | Tab switch-pane | p/Esc close | q quit\n"
        "space select | c copy-to-pane | m move-to-pane | d trash | r rename | z undo\n"
            "n new-file | N new-dir | G go | : palette"
    )

def test_select_help_bar_for_attribute_dialog() -> None:
    state = replace(build_initial_app_state(), ui_mode="DETAIL")

    help_state = select_help_bar_state(state)

    assert help_state.text == "enter close | esc close"

def test_select_help_bar_for_busy_mode() -> None:
    state = replace(build_initial_app_state(), ui_mode="BUSY")

    help_state = select_help_bar_state(state)

    assert help_state.text == "processing..."

def test_select_help_bar_for_delete_confirmation() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="CONFIRM",
        delete_confirmation=DeleteConfirmationState(
            paths=(TEST_PROJECT_ROOT + '/docs',),
        ),
    )

    help_state = select_help_bar_state(state)

    assert help_state.text == "enter confirm move to trash | esc cancel"

def test_select_help_bar_for_name_conflict() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="CONFIRM",
        name_conflict=NameConflictState(kind="create_file", name="docs"),
    )

    help_state = select_help_bar_state(state)

    assert help_state.text == "enter return to input | esc return to input"

def test_select_help_bar_for_paste_conflict_uses_generic_guidance() -> None:
    conflict = PasteConflict(
        source_path=TEST_PROJECT_ROOT + '/docs',
        destination_path=TEST_PROJECT_ROOT + '/docs',
    )
    state = replace(
        build_initial_app_state(),
        ui_mode="CONFIRM",
        paste_conflict=PasteConflictState(
            request=PasteRequest(
                mode="copy",
                source_paths=(TEST_PROJECT_ROOT + '/docs',),
                destination_dir=TEST_PROJECT_ROOT,
            ),
            conflicts=(conflict,),
            first_conflict=conflict,
        ),
    )

    help_state = select_help_bar_state(state)

    assert help_state.text == "resolve conflict in dialog"

def test_select_help_bar_for_permanent_delete_confirmation() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="CONFIRM",
        delete_confirmation=DeleteConfirmationState(
            paths=(TEST_PROJECT_ROOT + '/docs',),
            mode="permanent",
        ),
    )

    help_state = select_help_bar_state(state)

    assert help_state.text == "enter confirm permanently delete | esc cancel"

def test_select_help_bar_state_for_command_palette() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(),
    )

    help_bar = select_help_bar_state(state)

    assert help_bar.lines == (
        "type command | ↑↓ or Ctrl+j/k select | enter run | esc cancel",
    )

def test_select_help_bar_state_for_config_editor() -> None:
    state = replace(
        build_initial_app_state(config_path="/tmp/zivo/config.toml"),
        ui_mode="CONFIG",
        config_editor=ConfigEditorState(
            path="/tmp/zivo/config.toml",
            draft=build_initial_app_state().config,
        ),
    )

    help_bar = select_help_bar_state(state)

    assert help_bar.lines == (
        "↑↓ or Ctrl+j/k choose | ←→ or Enter change | s save | e advanced config",
        "esc close",
    )

def test_select_help_bar_state_for_file_search_palette() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(source="file_search"),
    )

    help_bar = select_help_bar_state(state)

    assert help_bar.lines == (
        "type filename | ↑↓ or Ctrl+j/k select | enter jump | "
        "Ctrl+w workspace | Ctrl+e edit | Ctrl+o GUI | esc cancel",
    )

def test_select_help_bar_state_for_filter_mode() -> None:
    state = _reduce_state(build_initial_app_state(), BeginFilterInput())

    help_state = select_help_bar_state(state)

    assert help_state.text == "type filter | enter/down apply | esc clear"

def test_select_help_bar_state_for_grep_search_palette() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="PALETTE",
        command_palette=CommandPaletteState(source="grep_search"),
    )

    help_bar = select_help_bar_state(state)

    assert help_bar.lines == (
        "type text / tab fields / ↑↓ or Ctrl+j/k select | "
        "enter jump | Ctrl+e edit | Ctrl+o GUI | "
        "Ctrl+x export | esc cancel",
    )

def test_select_input_bar_state_for_create_mode() -> None:
    state = _reduce_state(build_initial_app_state(), BeginCreateInput("file"))
    state = replace(
        state,
        pending_input=PendingInputState(
            prompt="Name or path: ", value="notes.txt", create_kind="file"
        ),
    )

    input_dialog = select_input_dialog_state(state)

    assert input_dialog is not None
    assert input_dialog.title == "Create"
    assert input_dialog.prompt == "Name or path: "
    assert input_dialog.value == "notes.txt"
    assert input_dialog.hint == "tab switch type | enter apply | esc cancel"

def test_select_input_dialog_state_shows_recursive_safety_details() -> None:
    state = build_initial_app_state()
    target = state.current_pane.entries[0]
    state = replace(
        state,
        ui_mode="CHMOD",
        pending_input=PendingInputState(
            prompt="Permissions: ",
            value="755",
            chmod_target_paths=(target.path,),
        ),
    )

    input_dialog = select_input_dialog_state(state)

    assert input_dialog is not None
    assert input_dialog.title == "Change Permissions"
    assert input_dialog.hint == "tab toggle recursive | enter apply | esc cancel"
    assert input_dialog.details == (
        "Targets: 1 (1 directory)",
        "Recursive: No",
        "Symlinks are skipped and never followed.",
    )

def test_select_input_bar_state_for_filter_mode() -> None:
    state = _reduce_state(build_initial_app_state(), BeginFilterInput())
    state = _reduce_state(state, SetFilterQuery("spec"))

    input_bar = select_input_bar_state(state)

    assert input_bar is not None
    assert input_bar.mode_label == "FILTER"
    assert input_bar.prompt == "Filter: "
    assert input_bar.value == "spec"
    assert input_bar.hint == "enter/down apply | esc clear"

def test_select_input_bar_state_for_pending_key_sequence() -> None:
    state = replace(
        build_initial_app_state(),
        pending_key_sequence=PendingKeySequenceState(
            keys=("y",),
            possible_next_keys=("y",),
        ),
        filter=replace(build_initial_app_state().filter, query="spec", active=True),
    )

    input_bar = select_input_bar_state(state)

    assert input_bar is not None
    assert input_bar.mode_label == "KEYS"
    assert input_bar.prompt == "Prefix: "
    assert input_bar.value == "y"
    assert input_bar.hint == "await y | esc cancel"

def test_select_input_bar_state_formats_extract_mode() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="EXTRACT",
        pending_input=PendingInputState(
            prompt="Extract to: ",
            value="/tmp/output/archive",
            extract_source_path=TEST_PROJECT_ROOT + '/archive.zip',
        ),
    )

    input_state = select_input_dialog_state(state)

    assert input_state is not None
    assert input_state.title == "Extract"
    assert input_state.prompt == "Extract to: "
    assert input_state.hint == "enter apply | esc cancel"

def test_select_input_bar_state_formats_zip_mode() -> None:
    state = replace(
        build_initial_app_state(),
        ui_mode="ZIP",
        pending_input=PendingInputState(
            prompt="Compress to: ",
            value="/tmp/output.zip",
            zip_source_paths=(TEST_PROJECT_ROOT + '/docs',),
        ),
    )

    input_state = select_input_dialog_state(state)

    assert input_state is not None
    assert input_state.title == "Compress"
    assert input_state.prompt == "Compress to: "
    assert input_state.hint == "enter apply | esc cancel"

def test_select_input_bar_state_keeps_active_filter_visible_after_confirm() -> None:
    state = _reduce_state(build_initial_app_state(), BeginFilterInput())
    state = _reduce_state(state, SetFilterQuery("spec"))
    state = _reduce_state(state, ConfirmFilterInput())

    input_bar = select_input_bar_state(state)

    assert input_bar is not None
    assert input_bar.mode_label == "FILTER"
    assert input_bar.prompt == "Filter: "
    assert input_bar.value == "spec"
    assert input_bar.hint == "esc clear"

def test_select_status_bar_exposes_notification_level() -> None:
    state = build_initial_app_state()
    state = _reduce_state(
        state,
        SetNotification(NotificationState(level="error", message="load failed")),
    )

    status = select_status_bar_state(state)

    assert status.message == "load failed"
    assert status.message_level == "error"
