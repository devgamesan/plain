"""Backward-compatible imports for state test support.

New tests should import from :mod:`tests.support.state` directly. Keeping this
small forwarding module avoids making the first support extraction a broad
rename-only change.
"""

from tests.support.state import entry, pane, reduce_state, replace_pane

__all__ = ["entry", "pane", "reduce_state", "replace_pane"]
