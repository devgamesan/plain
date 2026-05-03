"""XTerm parser monkey-patching to filter terminal response sequences."""

import re

from textual import events
from textual.keys import Keys

_TEXTUAL_TERMINAL_RESPONSE_FILTERS_INSTALLED = False
_TERMINAL_DEVICE_ATTRIBUTES_RESPONSE_RE = re.compile(r"\x1b\[(?:\?[\d;]*|[\d;]*)c\Z")
_TERMINAL_WINDOW_RESPONSE_RE = re.compile(r"\x1b\[(?:4|6|8);[\d;]+t\Z")
_TERMINAL_COLOR_RESPONSE_RE = re.compile(r"\x1b\]1[01];.*(?:\x07|\x1b\\)\Z", re.DOTALL)
_ESCAPE = "\x1b"
_OSC_INTRODUCER = "]"
_OSC_TERMINATOR = "\\"
_OSC_BEL = "\x07"


def _is_terminal_response_final_byte(key: str) -> bool:
    if len(key) != 1:
        return False
    codepoint = ord(key)
    return 0x40 <= codepoint <= 0x7E


def _install_textual_terminal_response_filters() -> None:
    global _TEXTUAL_TERMINAL_RESPONSE_FILTERS_INSTALLED
    if _TEXTUAL_TERMINAL_RESPONSE_FILTERS_INSTALLED:
        return

    import textual._xterm_parser as xterm_parser

    original_feed = xterm_parser.XTermParser.feed
    original = xterm_parser.XTermParser._sequence_to_key_events

    def _filter_terminal_response_chunk(self, data: str) -> str:
        pending_escape = getattr(self, "_zivo_pending_escape", False)
        in_osc = getattr(self, "_zivo_in_osc", False)
        osc_saw_escape = getattr(self, "_zivo_osc_saw_escape", False)

        if not data:
            if pending_escape and not in_osc:
                data = _ESCAPE
            else:
                data = ""
            pending_escape = False
            in_osc = False
            osc_saw_escape = False
            self._zivo_pending_escape = pending_escape
            self._zivo_in_osc = in_osc
            self._zivo_osc_saw_escape = osc_saw_escape
            return data

        filtered: list[str] = []
        index = 0

        if pending_escape:
            pending_escape = False
            if data.startswith(_OSC_INTRODUCER):
                in_osc = True
                index = 1
            else:
                filtered.append(_ESCAPE)

        while index < len(data):
            character = data[index]
            if in_osc:
                if osc_saw_escape:
                    osc_saw_escape = False
                    if character == _OSC_TERMINATOR:
                        in_osc = False
                    index += 1
                    continue
                if character == _OSC_BEL:
                    in_osc = False
                    index += 1
                    continue
                if character == _ESCAPE:
                    osc_saw_escape = True
                index += 1
                continue

            if character == _ESCAPE:
                next_index = index + 1
                if next_index >= len(data):
                    pending_escape = True
                    index += 1
                    continue
                if data[next_index] == _OSC_INTRODUCER:
                    in_osc = True
                    index += 2
                    continue

            filtered.append(character)
            index += 1

        self._zivo_pending_escape = pending_escape
        self._zivo_in_osc = in_osc
        self._zivo_osc_saw_escape = osc_saw_escape
        return "".join(filtered)

    def _wrapped_feed(self, data: str):
        filtered = _filter_terminal_response_chunk(self, data)
        if data and not filtered:
            return ()
        return original_feed(self, filtered)

    def _wrapped(self, sequence: str):
        if (
            _TERMINAL_DEVICE_ATTRIBUTES_RESPONSE_RE.fullmatch(sequence)
            or _TERMINAL_WINDOW_RESPONSE_RE.fullmatch(sequence)
            or _TERMINAL_COLOR_RESPONSE_RE.fullmatch(sequence)
        ):
            yield events.Key(Keys.Ignore, sequence)
            return
        yield from original(self, sequence)

    def _mouse_code_to_key_event(code: str) -> events.Key | None:
        sgr_match = xterm_parser.XTermParser._re_sgr_mouse.match(code)
        if sgr_match:
            buttons = int(sgr_match.group(1))
            state = sgr_match.group(4)
            if state == "M":
                if buttons == 8:
                    return events.Key("mouse_back", None)
                if buttons == 9:
                    return events.Key("mouse_forward", None)
        return None

    original_parse_mouse_code = xterm_parser.XTermParser.parse_mouse_code

    def _wrapped_parse_mouse_code(self, code: str) -> events.Message | None:
        key_event = _mouse_code_to_key_event(code)
        if key_event is not None:
            return key_event
        return original_parse_mouse_code(self, code)

    xterm_parser.XTermParser.feed = _wrapped_feed
    xterm_parser.XTermParser._sequence_to_key_events = _wrapped
    xterm_parser.XTermParser.parse_mouse_code = _wrapped_parse_mouse_code
    _TEXTUAL_TERMINAL_RESPONSE_FILTERS_INSTALLED = True
