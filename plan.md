## Plan for Issue #764

### 1. 目的
`split_terminal` 機能は非サポートとなったが、`app.py:494` で `self._app_state.split_terminal` を参照する残存コードにより `AttributeError` が発生する。この残骸を完全に除去する。

### 2. ベースブランチ
- `develop`

### 3. 実装方針
以下の全ファイルから `split_terminal` / `SplitTerminal` に関連するコード・CSS・アクションクラス・テスト・ドキュメント記述を削除する。

### 4. 実装ステップ

| # | ファイル | 内容 |
|---|---------|------|
| 1 | `src/zivo/app.py` | `SplitTerminalOutput` / `SplitTerminalExitedMessage` Message クラス削除 |
| 2 | `src/zivo/app.py` | `_update_split_terminal_overlay_geometry` メソッド削除 |
| 3 | `src/zivo/app.py` | `on_paste` 内の `split_terminal` 分岐削除、docstring 修正 |
| 4 | `src/zivo/app.py` | `_sync_overlay_layout` 内の呼び出し削除 |
| 5 | `src/zivo/app.py` | `#split-terminal-layer` の remove 処理削除 |
| 6 | `src/zivo/app.py` | `on_resize` の docstring 修正 |
| 7 | `src/zivo/state/actions.py` | `SplitTerminal*` の import と union type 参照削除 |
| 8 | `src/zivo/state/actions_runtime.py` | `SplitTerminal*` クラス定義削除 |
| 9 | `src/zivo/state/reducer_config.py` | `display.split_terminal_position` handler 削除 |
| 10 | `src/zivo/app.tcss` | `.split-terminal-overlay-layer` と `#split-terminal` 全スタイル削除 |
| 11 | `tests/test_app_runtime.py` | `_split_terminal_service` / `_split_terminal_session` モック削除 |
| 12 | `tests/state_selectors_cases.py` | `test_select_help_bar_for_split_terminal_focus` テスト削除 |
| 13 | `docs/architecture.md` | `Split["split_terminal.py"]` と説明文削除 |
| 14 | `docs/architecture.en.md` | `Split["split_terminal.py"]` と説明文削除 |

### 5. テスト方針
- `uv run pytest` で既存テスト全件が通ることを確認
- `uv run ruff check .` で lint 通過を確認
