"""Ensure standard help only advertises keys supported by its dispatchers."""

from zivo.state.input_browsing import BROWSING_HELP_LINES, BROWSING_KEYMAP
from zivo.state.input_transfer import TRANSFER_HELP_LINES, TRANSFER_KEYMAP

REMOVED_DIRECT_KEYS = {"i", "C", "B", "G", "M", "O", "T", "H", "R"}


def test_browsing_help_shortcuts_are_backed_by_the_browsing_keymap() -> None:
    advertised_keys = {
        key
        for line in BROWSING_HELP_LINES
        for key, _label in line
        if key not in {"[ ]"}
    }

    assert advertised_keys <= BROWSING_KEYMAP.keys()
    assert {"[", "]"} <= BROWSING_KEYMAP.keys()


def test_transfer_help_shortcuts_are_backed_by_the_transfer_keymap() -> None:
    advertised_keys = set()
    for line in TRANSFER_HELP_LINES:
        for key, _label in line:
            if key in {"[ ]", "p/Esc"}:
                continue
            advertised_keys.add(key)

    assert advertised_keys <= TRANSFER_KEYMAP
    assert {"[", "]", "p", "escape"} <= TRANSFER_KEYMAP


def test_low_frequency_direct_keys_are_removed_from_standard_keymaps() -> None:
    assert REMOVED_DIRECT_KEYS.isdisjoint(BROWSING_KEYMAP)
    assert REMOVED_DIRECT_KEYS.isdisjoint(TRANSFER_KEYMAP)
