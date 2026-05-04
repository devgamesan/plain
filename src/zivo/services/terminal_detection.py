"""Terminal capability detection for advanced graphics features."""

import os


def supports_kitty_graphics() -> bool:
    """Detect whether the terminal supports the Kitty graphics protocol.

    Checks environment variables set by known Kitty-protocol-capable
    terminals (Kitty, Ghostty, WezTerm, etc.).

    Returns:
        True if the terminal appears to support Kitty graphics protocol,
        False otherwise.
    """
    # Kitty terminal (the reference implementation)
    if os.environ.get("KITTY_WINDOW_ID", "").strip():
        return True
    if os.environ.get("KITTY_PID", "").strip():
        return True

    # Ghostty terminal
    if os.environ.get("GHOSTTY_RESOURCES_DIR", "").strip():
        return True

    # TERM_PROGRAM is set by many modern terminals
    term_program = os.environ.get("TERM_PROGRAM", "")
    if term_program.lower() in {"kitty", "ghostty"}:
        return True

    # TERM fallback
    term = os.environ.get("TERM", "")
    if "kitty" in term.lower() or "ghostty" in term.lower():
        return True

    return False
