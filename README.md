# Plain

Plain は Textual ベースで実装するシンプルな TUI ファイルマネージャです。  
このリポジトリでは、MVP に向けた Python 3.12+ / Textual の開発基盤を `uv` 前提で管理します。

## セットアップ

```bash
uv sync --dev
```

## 起動

推奨:

```bash
uv run plain
```

代替:

```bash
uv run python -m plain
```

現在は起動時に `CWD` を実ファイルシステムから読み込み、親・中央・子の 3 ペインを非同期に初期化します。中央ペインは詳細表示、左右ペインは軽量表示で、カーソル移動時は必要なときだけ子ペインを再取得します。取得失敗はステータスバーの通知へ変換されます。

実装構造の全体像は [docs/architecture.md](docs/architecture.md) にまとめています。

## キーバインド

現在サポートしている主要キーは以下です。入力解釈は widget ごとではなく reducer 向け Action へ正規化されます。

| モード | キー | 挙動 |
| --- | --- | --- |
| `BROWSING` | `↑` / `↓` | 可視エントリ内でカーソル移動 |
| `BROWSING` | `Space` | 現在カーソル行の選択トグル後、次行へ移動 |
| `BROWSING` | `Esc` | 選択解除 |
| `BROWSING` | `Ctrl+F` | フィルタ入力開始 |
| `FILTER` | 文字キー | フィルタ文字列を更新 |
| `FILTER` | `Backspace` | フィルタ文字列を 1 文字削除 |
| `FILTER` | `Space` | 再帰フィルタ ON/OFF |
| `FILTER` | `Enter` | フィルタを確定して `BROWSING` に戻る |
| `FILTER` | `Esc` | フィルタを解除して `BROWSING` に戻る |
| `CONFIRM` | `Esc` | 確認モードを抜けて `BROWSING` に戻る |
| `BUSY` | 任意 | 入力を無視し、ステータスバーへ警告を表示 |

`←` / `→` / `Enter` による実ディレクトリ移動やオープンは、Action の拡張ポイントを残しつつ後続 Issue で実装します。

## テストと静的検査

```bash
uv run ruff check .
uv run pytest
```

## ディレクトリ構成

```text
src/plain/
  ui/        Textual App と UI コンポーネント
  state/     AppState / reducer / action など状態更新責務
  services/  非同期ユースケースや副作用のオーケストレーション
  adapters/  OS・ファイルシステムなど外部依存境界
  models/    ドメインデータや表示用モデル
tests/       スモークテスト
```

## 方針

- UI とロジックを分離する
- 状態更新責務を一箇所に寄せる
- キー入力は app 側で Action に正規化し、widget 側に分岐を持たせない
- OS 依存処理やファイル操作は adapter/service 側へ隔離する
- 実ファイルシステムの読み込みは service / adapter 境界で扱い、UI から分離する
- 子ペインはカーソル対象がディレクトリのときだけ更新し、不要な再取得を避ける
