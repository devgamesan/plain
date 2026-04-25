"""Keyboard dispatcher that normalizes Textual input into reducer actions."""

import string

from .input_browsing import BROWSING_KEYMAP, dispatch_browsing_input
from .input_common import BrowsingHandler, DispatchedActions, warn
from .input_dialogs import (
    dispatch_config_input,
    dispatch_confirm_input,
    dispatch_detail_input,
    dispatch_filter_input,
    dispatch_input_dialog_input,
    dispatch_shell_command_input,
)
from .input_palette import dispatch_command_palette_input
from .input_terminal import TERMINAL_KEYMAP, dispatch_split_terminal_input, terminal_has_focus
from .input_transfer import TRANSFER_KEYMAP, dispatch_transfer_input
from .models import AppState

PRINTABLE_BINDING_KEYS = tuple((*string.ascii_letters, *string.digits))
PALETTE_EXTRA_KEYS = ("shift+tab",)
CONFLICT_KEYMAP = {
    "escape": "cancel_conflict",
    "o": "overwrite",
    "s": "skip",
    "r": "rename",
}
_MULTI_KEY_COMMAND_DISPATCH: dict[tuple[str, ...], BrowsingHandler] = {}


def iter_bound_keys() -> tuple[str, ...]:
    """Return the keys that should be installed as app bindings."""

    return tuple(
        dict.fromkeys(
            (
                *BROWSING_KEYMAP.keys(),
                *CONFLICT_KEYMAP.keys(),
                *TERMINAL_KEYMAP.keys(),
                *PRINTABLE_BINDING_KEYS,
                *PALETTE_EXTRA_KEYS,
                *tuple(
                    dict.fromkeys(
                        key
                        for sequence in _MULTI_KEY_COMMAND_DISPATCH
                        for key in sequence
                    )
                ),
                *TRANSFER_KEYMAP,
            )
        )
    )


def dispatch_key_input(
    state: AppState,
    *,
    key: str,
    character: str | None = None,
) -> DispatchedActions:
    """データドリブンなキーディスパッチ."""
    character = _normalize_input_character(state, key=key, character=character)

    if terminal_has_focus(state):
        return dispatch_split_terminal_input(state, key=key, character=character)
    if state.ui_mode == "FILTER":
        return dispatch_filter_input(state, key=key, character=character)
    if state.ui_mode == "CONFIRM":
        return dispatch_confirm_input(state, key=key, character=character)
    if state.ui_mode == "DETAIL":
        return dispatch_detail_input(state, key=key, character=character)
    if state.ui_mode == "CONFIG":
        return dispatch_config_input(state, key=key, character=character)
    if state.ui_mode == "BUSY":
        return warn("Input ignored while processing")
    if state.ui_mode == "PALETTE":
        return dispatch_command_palette_input(state, key=key, character=character)
    if state.ui_mode in {"RENAME", "CREATE", "EXTRACT", "ZIP"}:
        return dispatch_input_dialog_input(state, key=key, character=character)
    if state.ui_mode == "SHELL":
        return dispatch_shell_command_input(state, key=key, character=character)
    if state.layout_mode == "transfer":
        return dispatch_transfer_input(state, key=key, character=character)
    return dispatch_browsing_input(
        state,
        key=key,
        character=character,
        multi_key_command_dispatch=_MULTI_KEY_COMMAND_DISPATCH,
    )


def _normalize_input_character(
    state: AppState,
    *,
    key: str,
    character: str | None,
) -> str | None:
    resolved_character = _resolve_printable_character(key=key, character=character)
    if resolved_character is None:
        return None

    if terminal_has_focus(state):
        return resolved_character

    if state.ui_mode in {"PALETTE", "RENAME", "CREATE", "EXTRACT", "ZIP", "SHELL"}:
        return resolved_character

    if state.ui_mode == "FILTER" and not resolved_character.isspace():
        return resolved_character

    return None


def _resolve_printable_character(*, key: str, character: str | None) -> str | None:
    if character is not None and character.isprintable():
        return character

    if key == "space":
        return " "

    if len(key) == 1 and key.isprintable():
        return key

    return None
