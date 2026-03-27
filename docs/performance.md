# Plain 性能確認メモ

このメモは、MVP 判定向けに Issue #24 で実施した主要フロー結合テストと 1000 件規模確認の条件を残すためのものです。

## 実施日

- 2026-03-27

## 確認環境

- OS: Linux 6.17.0-19-generic
- Python: 3.12.3
- 実行方法: `uv run pytest`

## 自動確認の内容

- `tests/test_app.py::test_app_main_flow_round_trip_on_live_filesystem`
  - 実 filesystem を使って起動、移動、選択、copy、paste、filter、sort 切替を 1 本のシナリオで確認
- `tests/test_app.py::test_app_large_directory_smoke_with_1000_entries`
  - 200 ディレクトリ + 800 ファイルの合計 1000 件を生成
  - 初期表示、一覧 1000 件表示、150 行分のカーソル移動、子ペイン更新継続を確認

## 観察結果

- `uv run pytest tests/test_app.py -k large_directory_smoke_with_1000_entries --durations=1 -q`
  - `20.30s call     tests/test_app.py::test_app_large_directory_smoke_with_1000_entries`
  - 上記時間にはテストデータ生成、Textual headless 起動、150 回のキー送信が含まれる
- `uv run pytest tests/test_app.py -k 'main_flow_round_trip_on_live_filesystem or large_directory_smoke_with_1000_entries'`
  - `2 passed, 38 deselected in 21.92s`
- 1000 件規模でも headless の結合スモークは完走し、一覧表示と子ペイン更新が途中で止まる症状は再現しなかった

## 既知の制約

- 現在の測定は CI 向け benchmark ではなく、回帰検知用のスモーク確認である
- 記録している時間はテスト全体の実行時間であり、純粋な描画時間だけを切り出した数値ではない
- 実ターミナルでの体感速度やスクロール描画コストは、端末エミュレータやフォント設定の影響を受ける

## 再実行コマンド

```bash
uv run pytest tests/test_app.py -k large_directory_smoke_with_1000_entries --durations=1 -q
uv run pytest tests/test_app.py -k main_flow_round_trip_on_live_filesystem -q
```
