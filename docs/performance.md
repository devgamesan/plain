# Peneo 性能確認メモ

このメモは、MVP 判定向けに Issue #24 で実施した主要フロー結合テストと 1000 件規模確認の条件を残すためのものです。

## 目次

1. [スモークテスト（既存）](#スモークテスト既存)
2. [ベンチマーク基盤](#ベンチマーク基盤)
3. [ベンチマークの実行](#ベンチマークの実行)
4. [パフォーマンス回帰検知](#パフォーマンス回帰検知)

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

## ベンチマーク基盤

Issue #279 で導入されたベンチマーク基盤により、主要な操作のパフォーマンスを継続的に測定できるようになりました。

### 測定対象

1. **起動時間**
   - `import peneo`: モジュールインポート時間
   - `peneo --help`: ヘルプ表示の起動時間
   - `peneo init bash`: シェル統合スクリペット出力の起動時間

2. **ディレクトリ操作**
   - `LocalFilesystemAdapter.list_directory`: ディレクトリスキャン
   - `DirectorySizeService.calculate_directory_sizes`: ディレクトリサイズ計算

3. **セレクタ操作**
   - `select_shell_data()`: UI データ構築
   - `list_matching_directory_paths()`: go-to-path 候補生成
   - `get_command_palette_items()`: コマンドパレットアイテム生成

4. **検索操作**
   - ファイル検索: ファイル名による検索
   - grep 検索: ファイル内容による検索

### ベンチマーク Baseline（2026-04-04）

以下は、開発環境での初期測定値です。これらを baseline として、パフォーマンス改善の比較に使用します。

#### 起動時間

| 操作 | 平均時間 | 許容範囲 | 備考 |
|------|----------|----------|------|
| `import peneo` | ~200ms | 180-220ms | モジュールインポート |
| `peneo --help` | ~200-245ms | 270ms | ヘルプ表示 |
| `peneo init bash` | ~244ms | 270ms | シェル統合出力 |

#### ディレクトリ操作

| 操作 | データ规模 | 平均時間 | 許容範囲 |
|------|------------|----------|----------|
| `list_directory` | 1k entries | ~数ms | <1.0s |
| `list_directory` | 10k entries | ~数十ms | <1.0s |
| `calculate_directory_sizes` | 10 files | ~数百ms | <5.0s |

#### セレクタ操作

| 操作 | データ规模 | 平均時間 | 許容範囲 |
|------|------------|----------|----------|
| `select_shell_data` | 1k entries | ~1-2ms | <5ms |
| `select_shell_data` | 10k entries | ~4.2ms | <5ms |
| `list_matching_directory_paths` | 1k siblings | ~10ms | <12ms |
| `list_matching_directory_paths` | 5k siblings | ~33ms | <40ms |
| `get_command_palette_items` | 1k candidates | ~2ms | <3ms |
| `get_command_palette_items` | 5k candidates | ~8.25ms | <10ms |

#### 検索操作

| 操作 | データ规模 | 平均時間 | 許容範囲 |
|------|------------|----------|----------|
| ファイル検索 | 550 entries | ~数十ms | <1.0s |
| grep 検索 | 550 entries | ~数百ms | <2.0s |

**注記**: これらの値は開発環境での測定値であり、CI 環境では異なる場合があります。CI は相対比較用として使用してください。

---

## ベンチマークの実行

### ローカルでの実行

#### 全ベンチマーク実行

```bash
# すべてのベンチマークを実行
uv run pytest tests/test_benchmarks.py -v --durations=0

# または便利スクリプトを使用
./scripts/run_benchmarks.sh
```

#### 特定カテゴリの実行

```bash
# 起動時間のみ
uv run pytest tests/test_benchmarks.py::TestStartupBenchmarks -v

# ディレクトリ操作のみ
uv run pytest tests/test_benchmarks.py::TestDirectoryBenchmarks -v

# セレクタ操作のみ
uv run pytest tests/test_benchmarks.py::TestSelectorBenchmarks -v

# 検索操作のみ
uv run pytest tests/test_benchmarks.py::TestSearchBenchmarks -v
```

#### CI 向け高速ベンチマーク

CI で実行する高速ベンチマーク（`TestQuickBenchmarks`）は、manual workflow で `benchmark_type=quick` を指定した場合に実行されます：

```bash
# ローカルでも実行可能
uv run pytest tests/test_benchmarks.py::TestQuickBenchmarks -v
```

### CI での実行

GitHub Actions の manual workflow を使用してベンチマークを実行できます：

```bash
# CLI から手動実行（quick benchmark）
gh workflow run benchmark.yml -f benchmark_type=quick

# CLI から手動実行（full benchmark）
gh workflow run benchmark.yml -f benchmark_type=full

# または GitHub Web UI から "Benchmark" workflow を実行
```

実行結果は GitHub Actions の artifacts として保存され、ダウンロードできます。

---

## パフォーマンス回帰検知

### 回帰検出の閾値

以下の閾値を超える変化を検出した場合、パフォーマンス回帰または改善とみなします：

- **回帰**: 10% 以上遅い
- **改善**: 20% 以上早い

これらの閾値は、測定のノイズと CI 環境の変動を考慮して設定されています。

### 回帰検知の手順

1. **ベンチマークを実行**: 現在のコードでベンチマークを実行
2. **Baseline と比較**: 上記の baseline 値と比較
3. **閾値を確認**: 10% 以上の遅延がないか確認
4. **原因の調査**: 回帰が検出された場合は、変更履歴から原因を特定

### CI での自動検知

CI で実行される高速ベンチマーク（`TestQuickBenchmarks`）は、以下の条件で失敗します：

- 起動時間が 300ms を超える
- ディレクトリ操作が 500ms を超える
- セレクタ操作が 5ms を超える

これらの閾値を超えた場合、CI が失敗し、パフォーマンス回帰が通知されます。

**注記**: ベンチマークは manual workflow でのみ実行されるため、CI の失敗はベンチマーク実行時にのみ検知されます。

### 既知の制約

- **環境依存**: 測定値はハードウェア、OS、負荷状況に依存します
- **ノイズ**: 同じ環境でも測定ごとに数％の変動があります
- **CI 変動**: CI 環境ではローカルよりも時間がかかる場合があります

### 回帰時の対処

1. **再実行**: ノイズの可能性があるため、一度再実行してください
2. **変更の確認**: 最近の変更から原因となるコミットを特定
3. **プロファイリング**: `cProfile` や `line_profiler` を使用してボトルネックを特定
4. **修正と検証**: 修正後に再度ベンチマークを実行して改善を確認
