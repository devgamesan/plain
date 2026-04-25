"""Textual UI components for zivo."""

import sys

from .attribute_dialog import AttributeDialog
from .command_palette import CommandPalette
from .config_dialog import ConfigDialog
from .conflict_dialog import ConflictDialog
from .current_path_bar import CurrentPathBar
from .help_bar import HelpBar
from .input_bar import InputBar
from .input_dialog import InputDialog
from .panes import ChildPane, MainPane, SidePane
from .shell_command_dialog import ShellCommandDialog

if sys.platform != "win32":
    from .split_terminal import SplitTerminalPane
else:
    SplitTerminalPane = None  # type: ignore[misc,assignment]
from .status_bar import StatusBar
from .summary_bar import SummaryBar
from .tab_bar import TabBar

__all__ = [
    "AttributeDialog",
    "CommandPalette",
    "ConfigDialog",
    "ConflictDialog",
    "CurrentPathBar",
    "ChildPane",
    "HelpBar",
    "InputBar",
    "InputDialog",
    "MainPane",
    "SidePane",
    "ShellCommandDialog",
    "SplitTerminalPane",
    "StatusBar",
    "SummaryBar",
    "TabBar",
]
