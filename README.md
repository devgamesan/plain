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

現在は起動時に `CWD` を実ファイルシステムから読み込み、画面上部にカレントパス、その下に親・中央・子の 3 ペイン、ヘルプ行、rename/create 用の入力バー、ステータスバーを表示します。中央ペインは詳細表示、左右ペインは軽量表示で、カーソル移動時は必要なときだけ子ペインを再取得します。`←` / `→` / `Enter` / `Backspace` / `F5` によるディレクトリ移動と再読み込みに加えて、`Space` / `y` / `x` / `p` による選択と copy/cut/paste、`Delete` によるゴミ箱削除、`F2` / `Ctrl+N` / `Ctrl+Shift+N` による rename/create も reducer 経由で処理します。取得失敗やファイル操作結果はステータスバーの通知へ変換されます。

実装構造の全体像は [docs/architecture.md](docs/architecture.md) にまとめています。

## キーバインド

現在サポートしている主要キーは以下です。入力解釈は widget ごとではなく reducer 向け Action へ正規化されます。

| モード | キー | 挙動 |
| --- | --- | --- |
| `BROWSING` | `↑` / `↓` | 可視エントリ内でカーソル移動 |
| `BROWSING` | `←` / `Backspace` | 親ディレクトリへ移動 |
| `BROWSING` | `→` / `Enter` | カーソルがディレクトリならその中へ移動 |
| `BROWSING` | `F5` | カレントディレクトリを再読み込み |
| `BROWSING` | `Space` | 現在カーソル行の選択トグル後、次行へ移動 |
| `BROWSING` | `y` | 選択中の項目、またはカーソル項目をコピー対象として記録 |
| `BROWSING` | `x` | 選択中の項目、またはカーソル項目をカット対象として記録 |
| `BROWSING` | `p` | カレントディレクトリへ clipboard を貼り付け |
| `BROWSING` | `Esc` | 選択解除 |
| `BROWSING` | `/` | フィルタ入力開始 |
| `BROWSING` | `Delete` | 選択中の項目、またはカーソル項目をゴミ箱へ移動。複数対象時は確認ダイアログを表示 |
| `BROWSING` | `F2` | 単一対象のリネーム入力を開始 |
| `BROWSING` | `Ctrl+N` | 新規ファイル作成入力を開始 |
| `BROWSING` | `Ctrl+Shift+N` | 新規ディレクトリ作成入力を開始 |
| `FILTER` | 文字キー | フィルタ文字列を更新 |
| `FILTER` | `Backspace` | フィルタ文字列を 1 文字削除 |
| `FILTER` | `Space` | 再帰フィルタ ON/OFF |
| `FILTER` | `Enter` | フィルタを確定して `BROWSING` に戻る |
| `FILTER` | `Esc` | フィルタを解除して `BROWSING` に戻る |
| `RENAME` / `CREATE` | 文字キー | 入力バーの値を更新 |
| `RENAME` / `CREATE` | `Backspace` | 入力バーの値を 1 文字削除 |
| `RENAME` / `CREATE` | `Enter` | リネームまたは新規作成を実行 |
| `RENAME` / `CREATE` | `Esc` | 入力をキャンセルして `BROWSING` に戻る |
| `CONFIRM` | `o` / `s` / `r` / `Esc` | 競合ダイアログで overwrite / skip / rename / cancel を選ぶ |
| `CONFIRM` | `Enter` / `Esc` | 削除確認ダイアログで confirm / cancel を選ぶ |
| `BUSY` | 任意 | 入力を無視し、ステータスバーへ警告を表示 |

ファイル cursor 上の `Enter` / `→` による open はまだ未実装で、warning 通知を表示します。

選択はカレントディレクトリ単位で管理します。別ディレクトリへ移動した場合は選択を解除し、同じディレクトリの再読み込みではまだ存在する選択だけを維持します。copy は clipboard を維持し、cut は貼り付けで 1 件以上成功した時点で clipboard を空にします。cut 中の項目は一覧上で dim 表示し、保留中の移動対象であることを見分けられるようにしています。

貼り付け先に同名項目がある場合は競合ダイアログを表示し、MVP では選択した方針を残りの競合にも一括適用します。削除は OS のゴミ箱移動で実行し、複数対象時のみ確認ダイアログを挟みます。rename は単一対象に限定し、新規作成とあわせて画面下部の入力バーで値を編集します。通常の 1 行ヘルプには `F2` / `Ctrl+N` / `Ctrl+Shift+N` を表示します。バリデーションや重複名エラー時は入力値を保持したままエラー通知を表示します。

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
