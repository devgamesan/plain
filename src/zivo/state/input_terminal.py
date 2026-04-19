"""Split terminal key bindings and dispatcher."""

from .actions import SendSplitTerminalInput, ToggleSplitTerminal
from .input_common import DispatchedActions, supported
from .models import AppState

TERMINAL_KEYMAP = {
    "tab": "terminal_tab",
    "ctrl+q": "close_terminal",
    "enter": "terminal_enter",
    "backspace": "terminal_backspace",
    "escape": "terminal_escape",
    "delete": "terminal_delete",
    "home": "terminal_home",
    "end": "terminal_end",
    "pageup": "terminal_pageup",
    "pagedown": "terminal_pagedown",
    "up": "terminal_up",
    "down": "terminal_down",
    "left": "terminal_left",
    "right": "terminal_right",
    "ctrl+c": "terminal_ctrl_c",
    "insert": "terminal_passthrough",
    "f1": "terminal_passthrough",
    "f2": "terminal_passthrough",
    "f3": "terminal_passthrough",
    "f4": "terminal_passthrough",
    "f5": "terminal_passthrough",
    "f6": "terminal_passthrough",
    "f7": "terminal_passthrough",
    "f8": "terminal_passthrough",
    "f9": "terminal_passthrough",
    "f10": "terminal_passthrough",
    "f11": "terminal_passthrough",
    "f12": "terminal_passthrough",
    "shift+up": "terminal_passthrough",
    "shift+down": "terminal_passthrough",
    "shift+left": "terminal_passthrough",
    "shift+right": "terminal_passthrough",
    "ctrl+up": "terminal_passthrough",
    "ctrl+down": "terminal_passthrough",
    "ctrl+left": "terminal_passthrough",
    "ctrl+right": "terminal_passthrough",
    "shift+home": "terminal_passthrough",
    "shift+end": "terminal_passthrough",
    "ctrl+home": "terminal_passthrough",
    "ctrl+end": "terminal_passthrough",
    "ctrl+delete": "terminal_passthrough",
    "ctrl+insert": "terminal_passthrough",
    "ctrl+pageup": "terminal_passthrough",
    "ctrl+pagedown": "terminal_passthrough",
    "shift+pageup": "terminal_passthrough",
    "shift+pagedown": "terminal_passthrough",
    "shift+insert": "terminal_passthrough",
    "shift+delete": "terminal_passthrough",
    "ctrl+shift+up": "terminal_passthrough",
    "ctrl+shift+down": "terminal_passthrough",
    "ctrl+shift+left": "terminal_passthrough",
    "ctrl+shift+right": "terminal_passthrough",
    "ctrl+shift+home": "terminal_passthrough",
    "ctrl+shift+end": "terminal_passthrough",
    "ctrl+shift+pageup": "terminal_passthrough",
    "ctrl+shift+pagedown": "terminal_passthrough",
    "ctrl+shift+insert": "terminal_passthrough",
    "ctrl+shift+delete": "terminal_passthrough",
}

TERMINAL_KEY_SEQUENCES: dict[str, str] = {
    "escape": "\x1b",
    "f1": "\x1bOP",
    "f2": "\x1bOQ",
    "f3": "\x1bOR",
    "f4": "\x1bOS",
    "f5": "\x1b[15~",
    "f6": "\x1b[17~",
    "f7": "\x1b[18~",
    "f8": "\x1b[19~",
    "f9": "\x1b[20~",
    "f10": "\x1b[21~",
    "f11": "\x1b[23~",
    "f12": "\x1b[24~",
    "insert": "\x1b[2~",
    "delete": "\x1b[3~",
    "home": "\x1b[H",
    "end": "\x1b[F",
    "pageup": "\x1b[5~",
    "pagedown": "\x1b[6~",
    "up": "\x1b[A",
    "down": "\x1b[B",
    "right": "\x1b[C",
    "left": "\x1b[D",
    "shift+up": "\x1b[1;2A",
    "shift+down": "\x1b[1;2B",
    "shift+right": "\x1b[1;2C",
    "shift+left": "\x1b[1;2D",
    "ctrl+up": "\x1b[1;5A",
    "ctrl+down": "\x1b[1;5B",
    "ctrl+right": "\x1b[1;5C",
    "ctrl+left": "\x1b[1;5D",
    "ctrl+shift+up": "\x1b[1;6A",
    "ctrl+shift+down": "\x1b[1;6B",
    "ctrl+shift+right": "\x1b[1;6C",
    "ctrl+shift+left": "\x1b[1;6D",
    "shift+home": "\x1b[1;2H",
    "shift+end": "\x1b[1;2F",
    "ctrl+home": "\x1b[1;5H",
    "ctrl+end": "\x1b[1;5F",
    "ctrl+shift+home": "\x1b[1;6H",
    "ctrl+shift+end": "\x1b[1;6F",
    "ctrl+pageup": "\x1b[5;5~",
    "ctrl+pagedown": "\x1b[6;5~",
    "shift+pageup": "\x1b[5;2~",
    "shift+pagedown": "\x1b[6;2~",
    "ctrl+shift+pageup": "\x1b[5;6~",
    "ctrl+shift+pagedown": "\x1b[6;6~",
    "ctrl+insert": "\x1b[2;5~",
    "shift+insert": "\x1b[2;2~",
    "ctrl+delete": "\x1b[3;5~",
    "shift+delete": "\x1b[3;2~",
    "ctrl+shift+insert": "\x1b[2;6~",
    "ctrl+shift+delete": "\x1b[3;6~",
}


def terminal_has_focus(state: AppState) -> bool:
    return (
        state.ui_mode == "BROWSING"
        and state.split_terminal.visible
        and state.split_terminal.focus_target == "terminal"
    )


def dispatch_split_terminal_input(
    state: AppState,
    *,
    key: str,
    character: str | None,
) -> DispatchedActions:
    command = TERMINAL_KEYMAP.get(key)

    if command == "terminal_tab":
        return supported(SendSplitTerminalInput("\t"))

    if command == "close_terminal":
        return supported(ToggleSplitTerminal())

    sequence = TERMINAL_KEY_SEQUENCES.get(key)
    if sequence is not None:
        return supported(SendSplitTerminalInput(sequence))

    if key == "enter":
        return supported(SendSplitTerminalInput("\r"))

    if key == "backspace":
        return supported(SendSplitTerminalInput("\x7f"))

    control_character = terminal_control_character(key)
    if control_character is not None:
        return supported(SendSplitTerminalInput(control_character))

    if character and character.isprintable():
        return supported(SendSplitTerminalInput(character))

    return ()


def terminal_control_character(key: str) -> str | None:
    if not key.startswith("ctrl+") or key == "ctrl+q":
        return None

    suffix = key[5:]
    if len(suffix) != 1 or not suffix.isalpha():
        return None

    letter = suffix.lower()
    return chr(ord(letter) - ord("a") + 1)
