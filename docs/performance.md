# Zivo 性能確認メモ

このメモは、MVP 判定向けに Issue #24 で実施した主要フロー結合テストと 1000 件規模確認の条件を残すためのものです。

## 目次

1. [スモークテスト（既存）](#スモークテスト既存)
2. [Issue #304 viewport-aware projection スパイク](#issue-304-viewport-aware-projection-スパイク)
3. [Issue #646 ディレクトリ一覧メタデータ遅延取得](#issue-646-ディレクトリ一覧メタデータ遅延取得)
4. [Issue #647 ブラウザスナップショット段階ロード](#issue-647-ブラウザスナップショット段階ロード)
5. [現在の方針](#現在の方針)

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

## Issue #304 viewport-aware projection スパイク

### 実施日

- 2026-04-05

### 追加したもの

- `scripts/benchmark_current_pane_projection.py`
  - current pane の `cursor move` / `page scroll` / `selection toggle` / `directory size` 反映を、`full` と `viewport` で同条件比較する手動計測スクリプト
- `create_app(..., current_pane_projection_mode="viewport")`
  - `DataTable` は維持したまま、current pane の表示を terminal 高さ由来の window に絞る比較用スパイク
- Issue #326 での正式採用
  - 2026-04-05 に viewport-aware projection を通常起動の既定経路へ昇格し、`pageup` / `pagedown` / `home` / `end` / filter / sort / hidden-file toggle / reload / resize 後も window を正規化する回帰テストを追加した

### 計測条件

- Python: `uv run python`
- terminal height: 24
- viewport window: 16 rows
- 測定対象は `select_shell_data()` を中心にした projection/update hint 生成コスト
- CI benchmark ではなく、Issue #304 の判断材料を残すためのローカル手動計測

### 再実行コマンド

```bash
uv run python scripts/benchmark_current_pane_projection.py --entries 10000 --iterations 200
uv run python scripts/benchmark_current_pane_projection.py --entries 50000 --iterations 100
```

### 観察結果

#### 10,000 entries

| mode | operation | rendered rows | mean |
| --- | --- | ---: | ---: |
| full | cursor move | 10000 | 5.26 ms |
| full | page scroll | 10000 | 4.77 ms |
| full | selection toggle | 10000 | 5.27 ms |
| full | directory size reflect | 10000 | 8.55 ms |
| viewport | cursor move | 16 | 2.48 ms |
| viewport | page scroll | 16 | 2.48 ms |
| viewport | selection toggle | 16 | 2.42 ms |
| viewport | directory size reflect | 16 | 2.45 ms |

#### 50,000 entries

| mode | operation | rendered rows | mean |
| --- | --- | ---: | ---: |
| full | cursor move | 50000 | 26.59 ms |
| full | page scroll | 50000 | 24.39 ms |
| full | selection toggle | 50000 | 26.50 ms |
| full | directory size reflect | 50000 | 42.46 ms |
| viewport | cursor move | 16 | 12.25 ms |
| viewport | page scroll | 16 | 12.10 ms |
| viewport | selection toggle | 16 | 12.11 ms |
| viewport | directory size reflect | 16 | 12.27 ms |

### 判断メモ

- `DataTable` 自体を置き換えなくても、current pane の projection を window 化するだけで処理時間は一貫して下がった
- 改善幅は 10,000 entries で約 2 倍、50,000 entries では `directory size` 反映で約 3.5 倍
- 50,000 entries では viewport 化後も 12 ms 前後かかるため、selector 以外の比較的固定コストは残る
- つまり「仮想化は不要」とは言えず、少なくとも current pane 側で offscreen row を projection 対象から外す価値はある
- Issue #326 で、この方針を comparison-only spike から通常実装へ昇格した
- `current_pane_projection_mode` はベンチマークとテストのための内部切り替えとして残し、通常起動では viewport projection を使う

---

## Issue #646 ディレクトリ一覧メタデータ遅延取得

### 実施日

- 2026-04-20

### 追加したもの

- `scripts/benchmark_directory_listing.py`
  - `LocalFilesystemAdapter.list_directory()` と `inspect_entry()` を同じ fixture 条件で比較する手動ベンチマーク
- `tests/test_adapters_filesystem.py`
  - 一覧表示で owner/group 解決を呼ばないこと
  - ディレクトリ一覧の metadata を軽量化していること
  - 属性ダイアログ向け詳細取得で owner/group を含む metadata を取得できること

### 再実行コマンド

```bash
uv run python scripts/benchmark_directory_listing.py --files 8000 --dirs 2000 --iterations 10
```

### 判断メモ

- 一覧表示で必要な軽量データと、属性ダイアログ用の重い metadata 取得を分離した
- owner/group 解決は `Show attributes` 実行時の遅延取得へ移した
- 比較は同じコマンドを別 commit や branch で再実行して確認する

---

## Issue #647 ブラウザスナップショット段階ロード

### 実施日

- 2026-04-20

### 追加したもの

- `scripts/benchmark_progressive_loading.py`
  - blocking モード（既存の同期ロード）と progressive モード（新しい段階ロード）を比較する手動ベンチマーク
- `src/zivo/state/actions_runtime.py`
  - `CurrentPaneSnapshotLoaded`, `ParentChildSnapshotLoaded`, `ParentChildSnapshotFailed` アクション
  - `RequestBrowserSnapshot` に `progressive` フィールドを追加
- `src/zivo/state/effects.py`
  - `LoadCurrentPaneEffect`, `LoadParentChildEffect` エフェクト
- `src/zivo/state/models.py`
  - `BrowserTabState` に `parent_pane_loading`, `child_pane_loading` フィールドを追加
- `src/zivo/services/browser_snapshot.py`
  - `load_current_pane_snapshot()`, `load_parent_child_panes()` メソッド
- `src/zivo/app_runtime_search.py`
  - `schedule_progressive_browser_snapshot()`, `schedule_parent_child_update()` スケジューラ
- `src/zivo/state/reducer_navigation.py`
  - `_handle_current_pane_loaded()`, `_handle_parent_child_loaded()`, `_handle_parent_child_failed()` ハンドラー

### 再実行コマンド

```bash
uv run python scripts/benchmark_progressive_loading.py --files 100 --dirs 100 --iterations 10
```

### 観察結果

#### 100 files × 100 directories

| mode | operation | mean_ms | p95_ms |
| --- | --- | ---: | ---: |
| blocking | baseline | 1.68 | 8.86 |
| progressive | phase1 (first paint) | 0.04 | 0.04 |
| progressive | phase2 (parent+child) | 0.07 | 0.08 |
| progressive | total (phase1+2) | 0.11 | 0.12 |

**First Paint 改善**:
- blocking: 1.68 ms
- progressive: 0.04 ms
- **改善率: 42.45x 高速化**
- **削減時間: 1.64 ms**

### 判断メモ

- current pane を先に表示し、parent/child はバックグラウンドで非同期ロードする段階ロードを実装した
- First Paint レイテンシが **42.45x** に大幅改善された
- 完全なスナップショット（phase1+2）でも blocking モードより高速化されている
- 既存の `blocking=True` 動作は維持されている
- 比較は同じコマンドを別 commit や branch で再実行して確認する

---

## 現在の方針

- 自動ベンチマークは削除した
- CI と release workflow では通常のテストのみを実行する
- 通常起動の current pane は viewport-aware projection を使い、summary と selected count は全件基準のまま維持する
- 性能確認は必要な変更ごとに、人手で対象シナリオを決めて実施する
- 大規模 fixture や反復回数の多い性能計測を、日常の自動チェックへ戻さない

### 手動での性能確認例

```bash
uv run pytest tests/test_app.py -k large_directory_smoke_with_1000_entries --durations=1 -q
uv run pytest tests/test_app.py -k main_flow_round_trip_on_live_filesystem -q
uv run pytest tests/test_state_selectors.py -q
uv run python scripts/benchmark_current_pane_projection.py --entries 10000 --iterations 200
uv run python scripts/benchmark_directory_listing.py --files 8000 --dirs 2000 --iterations 10
uv run python scripts/benchmark_progressive_loading.py --files 100 --dirs 100 --iterations 10
```
