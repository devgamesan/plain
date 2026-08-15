# Test suite guide

テストは、プロダクトの責務に対応するテストモジュールと、複数モジュールで共有するサポートコードに分けます。

## 配置ルール

- `tests/test_*.py`: pytestが直接収集するテスト本体。別のテストモジュールをヘルパー目的でimportしない。
- `tests/support/`: state生成、Textual待機処理、Fakeサービスなどの共有テスト基盤。テスト関数は置かない。
- `tests/state_test_helpers.py`: 既存importとの互換用。新しいテストでは`tests.support.state`を使う。

主な機能別テストは次のように分かれています。

- App: `test_app_browsing.py`、`test_app_search.py`、`test_app_config.py`、`test_app_mutations.py`、`test_app_layout.py`
- Selector: `test_state_selectors_panes.py`、`test_state_selectors_palette.py`、`test_state_selectors_ui.py`
- Reducer: `test_state_reducer_core.py`、`test_state_reducer_config.py`、`test_state_reducer_input.py`、`test_state_reducer_snapshots.py`、`test_state_reducer_navigation_tabs.py`
- Browser snapshot: `test_services_browser_snapshot_core.py`、`test_services_browser_snapshot_preview.py`、`test_services_browser_snapshot_text.py`、`test_services_browser_snapshot_grep.py`

新しいテストを追加するときは、対象の振る舞いを直接表すモジュールに置き、共有化が必要になった処理だけを`tests/support/`へ抽出します。importの見通しを保つため、wildcard importは使用しません。

## 実行コマンド

```bash
uv run ruff check .
uv run pytest --collect-only -q
uv run pytest -q
```

Textual appや外部サービスを使うテストを分離して実行する場合は、機能別のテストファイルを指定します。実ファイルが必要なケースでは`tmp_path`を使い、テスト間で共有する固定ディレクトリを作らないようにします。
