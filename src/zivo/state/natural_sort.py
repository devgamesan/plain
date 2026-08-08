"""Natural (human-friendly) sort key helper.

Provides a single :func:`natural_sort_key` used by every name-based sort in
the application so that ordering is consistent across panes, search results,
path completion, and archive listings.
"""

import re

# ASCII digits only by design. Unicode digit classes (superscripts, other
# scripts' digits) are intentionally excluded for predictable ordering.
_NUMBER_PATTERN = re.compile(r"([0-9]+)")


def natural_sort_key(text: str) -> tuple:
    """Return a sort key that orders ``text`` in natural order.

    Numeric runs are compared by integer value, with the original digit
    string as a tie-breaker, so ``part01 < part1 < part2`` and
    ``file2 < file10``. Text segments are compared case-insensitively
    (``casefold``). When two names share the same segment key (e.g.
    ``File1`` / ``file1``), the original text breaks the tie deterministically
    so the order never depends on the OS scandir order.

    The returned ``(segments, text)`` pair keeps every comparison position
    type-safe: segments are compared position-by-position (a numeric segment
    ``(0, int, str)`` against another numeric segment, a text segment
    ``(1, str)`` against another text segment), and the trailing ``text``
    only participates once the segments fully match. That also makes a
    shorter name sort before a longer name that extends it (``a < a1``).
    """
    key = []
    for part in _NUMBER_PATTERN.split(text):
        if not part:
            continue
        # A captured group is always pure ASCII digits; a text part never
        # starts with an ASCII digit (it would otherwise have been matched).
        if "0" <= part[0] <= "9":
            key.append((0, int(part), part))
        else:
            key.append((1, part.casefold()))
    return (tuple(key), text)
