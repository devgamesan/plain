# Peneo 性能確認メモ

このメモは、MVP 判定向けに Issue #24 で実施した主要フロー結合テストと 1000 件規模確認の条件を残すためのものです。

## 目次

1. [スモークテスト（既存）](#スモークテスト既存)
2. [現在の方針](#現在の方針)

---

## スモークテスト（既存）

### 実施日

- 2026-03-27
- 2026-03-28

### 確認環境

- OS: Linux 6.17.0-19-generic
- Python: 3.12.3
- 実行方法: `uv run pytest`

### 自動確認の内容

- `tests/test_app.py::test_app_main_flow_round_trip_on_live_filesystem`
  - 実 filesystem を使って起動、移動、選択、copy、paste、filter、sort 切替を 1 本のシナリオで確認
- `tests/test_app.py::test_app_large_directory_smoke_with_1000_entries`
  - 200 ディレクトリ + 800 ファイルの合計 1000 件を生成
  - 初期表示、一覧 1000 件表示、150 行分のカーソル移動、子ペイン更新継続を確認

### 観察結果

- `uv run pytest tests/test_app.py -k large_directory_smoke_with_1000_entries --durations=1 -q`
  - `20.30s call     tests/test_app.py::test_app_large_directory_smoke_with_1000_entries`
  - 上記時間にはテストデータ生成、Textual headless 起動、150 回のキー送信が含まれる
- `uv run pytest tests/test_app.py -k 'main_flow_round_trip_on_live_filesystem or large_directory_smoke_with_1000_entries'`
  - `2 passed, 38 deselected in 21.92s`
- 1000 件規模でも headless の結合スモークは完走し、一覧表示と子ペイン更新が途中で止まる症状は再現しなかった
- 2026-03-28 の Issue #104 対応で、current pane の visible entries を `select_shell_data()` 内で使い回し、カーソル移動だけでは `MainPane` が `DataTable.clear()` / `add_row()` を呼ばない回帰テストを追加した
- `uv run python -m pytest tests/test_state_selectors.py -q`
  - `38 passed in 0.16s`
- `uv run python -m pytest tests/test_app.py -k 'refresh or large_directory_smoke_with_1000_entries' -q`
  - `4 passed, 41 deselected in 13.49s`
- 上記回帰確認では、1000 件一覧のスモークを維持したまま、単一カーソル移動で current pane 行を再構築しないことを検証した

### 既知の制約

- 現在の測定は CI 向け benchmark ではなく、回帰検知用のスモーク確認である
- 記録している時間はテスト全体の実行時間であり、純粋な描画時間だけを切り出した数値ではない
- 実ターミナルでの体感速度やスクロール描画コストは、端末エミュレータやフォント設定の影響を受ける

### 再実行コマンド

```bash
uv run pytest tests/test_app.py -k large_directory_smoke_with_1000_entries --durations=1 -q
uv run pytest tests/test_app.py -k main_flow_round_trip_on_live_filesystem -q
uv run python -m pytest tests/test_state_selectors.py -q
uv run python -m pytest tests/test_app.py -k 'refresh or large_directory_smoke_with_1000_entries' -q
```

---

## 現在の方針

- 自動ベンチマークは削除した
- CI と release workflow では通常のテストのみを実行する
- 性能確認は必要な変更ごとに、人手で対象シナリオを決めて実施する
- 大規模 fixture や反復回数の多い性能計測を、日常の自動チェックへ戻さない

### 手動での性能確認例

```bash
uv run pytest tests/test_app.py -k large_directory_smoke_with_1000_entries --durations=1 -q
uv run pytest tests/test_app.py -k main_flow_round_trip_on_live_filesystem -q
uv run pytest tests/test_state_selectors.py -q
```
