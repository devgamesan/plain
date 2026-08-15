"""Issue #1098: transfer モードの Create コマンド shortcut/label と実体の整合。

transfer モードに n（ファイル作成）直接キーを追加して browsing モードと対称化し、
パレットの Create 項目も実体（ファイル作成）に合わせて label="Create file",
shortcut="n" に是正する。
"""

import zivo.state.command_palette as command_palette_module
from tests.support.state import reduce_state as _reduce_state
from zivo.state import build_initial_app_state, dispatch_key_input
from zivo.state.actions import (
    BeginCommandPalette,
    BeginCreateInput,
    SetNotification,
    ToggleTransferMode,
)


def _transfer_mode_state():
    return _reduce_state(build_initial_app_state(), ToggleTransferMode())


def test_transfer_mode_n_creates_file() -> None:
    """transfer モードの n キーはファイル作成プロンプトを開く（browsing と対称）。"""
    state = _transfer_mode_state()

    assert dispatch_key_input(state, key="n") == (
        SetNotification(None),
        BeginCreateInput("file"),
    )


def test_transfer_mode_uppercase_n_creates_directory() -> None:
    """transfer モードの N キーはディレクトリ作成プロンプトを開く（従来挙動を維持）。"""
    state = _transfer_mode_state()

    assert dispatch_key_input(state, key="N") == (
        SetNotification(None),
        BeginCreateInput("dir"),
    )


def _transfer_palette_create_item():
    state = _transfer_mode_state()
    state = _reduce_state(state, BeginCommandPalette())
    items = command_palette_module.get_command_palette_items(state)
    return next(item for item in items if item.id == "create")


def test_transfer_palette_create_item_matches_file_creation() -> None:
    """transfer パレットの Create 項目は実体（ファイル作成）に一致する表示を持つ。"""
    create_item = _transfer_palette_create_item()

    assert create_item.label == "Create file"
    assert create_item.shortcut == "n"
