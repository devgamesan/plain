# ruff: noqa: F403,F405

from .input_dispatch_helpers import *


def test_split_terminal_focus_sends_printable_input() -> None:
    state = _focused_split_terminal_state()

    actions = dispatch_key_input(state, key="a", character="a")

    assert actions == (SetNotification(None), SendSplitTerminalInput("a"))


def test_split_terminal_focus_sends_bound_space_without_character() -> None:
    state = _focused_split_terminal_state()

    actions = dispatch_key_input(state, key="space")

    assert actions == (SetNotification(None), SendSplitTerminalInput(" "))


def test_split_terminal_focus_sends_delete_sequence() -> None:
    state = _focused_split_terminal_state()

    actions = dispatch_key_input(state, key="delete")

    assert actions == (SetNotification(None), SendSplitTerminalInput("\x1b[3~"))


def test_split_terminal_focus_sends_navigation_sequences() -> None:
    state = _focused_split_terminal_state()

    assert dispatch_key_input(state, key="home") == (
        SetNotification(None),
        SendSplitTerminalInput("\x1b[H"),
    )
    assert dispatch_key_input(state, key="end") == (
        SetNotification(None),
        SendSplitTerminalInput("\x1b[F"),
    )
    assert dispatch_key_input(state, key="pageup") == (
        SetNotification(None),
        SendSplitTerminalInput("\x1b[5~"),
    )
    assert dispatch_key_input(state, key="pagedown") == (
        SetNotification(None),
        SendSplitTerminalInput("\x1b[6~"),
    )


def test_split_terminal_focus_sends_tab() -> None:
    state = _focused_split_terminal_state()

    actions = dispatch_key_input(state, key="tab")

    assert actions == (SetNotification(None), SendSplitTerminalInput("\t"))


def test_split_terminal_focus_takes_priority_over_browsing_navigation() -> None:
    state = _focused_split_terminal_state()

    actions = dispatch_key_input(state, key="left")

    assert actions == (SetNotification(None), SendSplitTerminalInput("\x1b[D"))


def test_split_terminal_focus_sends_ctrl_shortcuts_except_ctrl_v() -> None:
    state = _focused_split_terminal_state()

    assert dispatch_key_input(state, key="ctrl+d") == (
        SetNotification(None),
        SendSplitTerminalInput("\x04"),
    )
    assert dispatch_key_input(state, key="ctrl+t") == (
        SetNotification(None),
        SendSplitTerminalInput("\x14"),
    )
    assert dispatch_key_input(state, key="ctrl+l") == (
        SetNotification(None),
        SendSplitTerminalInput("\x0c"),
    )


def test_split_terminal_escape_sends_esc_byte() -> None:
    state = _focused_split_terminal_state()

    actions = dispatch_key_input(state, key="escape")

    assert actions == (SetNotification(None), SendSplitTerminalInput("\x1b"))


def test_split_terminal_ctrl_q_closes_terminal() -> None:
    state = _focused_split_terminal_state()

    actions = dispatch_key_input(state, key="ctrl+q")

    assert actions == (SetNotification(None), ToggleSplitTerminal())


def test_split_terminal_function_keys_send_sequences() -> None:
    state = _focused_split_terminal_state()

    assert dispatch_key_input(state, key="f1") == (
        SetNotification(None),
        SendSplitTerminalInput("\x1bOP"),
    )
    assert dispatch_key_input(state, key="f5") == (
        SetNotification(None),
        SendSplitTerminalInput("\x1b[15~"),
    )
    assert dispatch_key_input(state, key="f12") == (
        SetNotification(None),
        SendSplitTerminalInput("\x1b[24~"),
    )


def test_split_terminal_insert_sends_sequence() -> None:
    state = _focused_split_terminal_state()

    actions = dispatch_key_input(state, key="insert")

    assert actions == (SetNotification(None), SendSplitTerminalInput("\x1b[2~"))


def test_split_terminal_modified_arrows_send_sequences() -> None:
    state = _focused_split_terminal_state()

    assert dispatch_key_input(state, key="shift+up") == (
        SetNotification(None),
        SendSplitTerminalInput("\x1b[1;2A"),
    )
    assert dispatch_key_input(state, key="ctrl+left") == (
        SetNotification(None),
        SendSplitTerminalInput("\x1b[1;5D"),
    )
    assert dispatch_key_input(state, key="ctrl+shift+right") == (
        SetNotification(None),
        SendSplitTerminalInput("\x1b[1;6C"),
    )


def test_split_terminal_modified_navigation_sends_sequences() -> None:
    state = _focused_split_terminal_state()

    assert dispatch_key_input(state, key="ctrl+home") == (
        SetNotification(None),
        SendSplitTerminalInput("\x1b[1;5H"),
    )
    assert dispatch_key_input(state, key="shift+end") == (
        SetNotification(None),
        SendSplitTerminalInput("\x1b[1;2F"),
    )
    assert dispatch_key_input(state, key="ctrl+pagedown") == (
        SetNotification(None),
        SendSplitTerminalInput("\x1b[6;5~"),
    )


def test_split_terminal_shift_delete_sends_sequence() -> None:
    state = _focused_split_terminal_state()

    actions = dispatch_key_input(state, key="shift+delete")

    assert actions == (SetNotification(None), SendSplitTerminalInput("\x1b[3;2~"))


def test_split_terminal_ctrl_q_is_not_sent_as_control_character() -> None:
    """Ctrl+Q should close terminal, not send the XON byte (\\x11)."""
    state = _focused_split_terminal_state()

    actions = dispatch_key_input(state, key="ctrl+q")

    assert actions == (SetNotification(None), ToggleSplitTerminal())


def test_split_terminal_iter_bound_keys_includes_new_keys() -> None:
    keys = iter_bound_keys()

    assert "ctrl+q" in keys
    assert "f1" in keys
    assert "f12" in keys
    assert "insert" in keys
    assert "ctrl+up" in keys
    assert "shift+left" in keys
    assert "ctrl+shift+right" in keys

