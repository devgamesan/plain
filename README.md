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

現在は起動時に `CWD` を実ファイルシステムから読み込み、画面上部にカレントパス、その下に親・中央・子の 3 ペイン、コマンドパレット、ヘルプ行、通知用ステータスバーを表示します。中央ペインでは `Current Directory` タイトル直下に `items / selected / sort` の要約行を出し、その下に `FILTER` / `RENAME` / `CREATE` の入力ラインを表示します。中央ペインは詳細表示、左右ペインは軽量表示で、カーソル移動時は必要なときだけ子ペインを再取得します。`←` / `→` / `Enter` / `Backspace` / `F5` によるディレクトリ移動と再読み込みに加えて、`s` / `d` による中央ペインのソート切替、`Space` / `y` / `x` / `p` による選択と copy/cut/paste、`Delete` によるゴミ箱削除、`F2` による rename、`:` によるコマンドパレット起動を reducer 経由で処理します。親・子ペインは補助表示として常に名前順かつディレクトリ優先で表示します。ファイル cursor 上の `Enter` / `→` は OS の既定アプリでファイルを開きます。コマンドパレット経由では `新規ファイル` / `新規ディレクトリ` / `Copy path` / `Open terminal here` / `Show hidden files` / `Hide hidden files` を実行でき、`Copy path` は選択中の絶対パス群、未選択時はカーソル対象の絶対パスをシステムクリップボードへコピーします。取得失敗やファイル操作結果は下段ステータスバーの通知へ変換されます。

実装構造の全体像は [docs/architecture.md](docs/architecture.md) にまとめています。

## キーバインド

現在サポートしている主要キーは以下です。入力解釈は widget ごとではなく reducer 向け Action へ正規化されます。

| モード | キー | 挙動 |
| --- | --- | --- |
| `BROWSING` | `↑` / `↓` | 可視エントリ内でカーソル移動 |
| `BROWSING` | `←` / `Backspace` | 親ディレクトリへ移動 |
| `BROWSING` | `→` / `Enter` | カーソルがディレクトリならその中へ移動、ファイルなら既定アプリで開く |
| `BROWSING` | `F5` | カレントディレクトリを再読み込み |
| `BROWSING` | `s` | 中央ペインのソートを `name asc -> name desc -> modified desc -> modified asc -> size desc -> size asc` の順で循環 |
| `BROWSING` | `d` | 中央ペインのディレクトリ優先表示 ON/OFF を切り替え |
| `BROWSING` | `Space` | 現在カーソル行の選択トグル後、次行へ移動 |
| `BROWSING` | `y` | 選択中の項目、またはカーソル項目をコピー対象として記録 |
| `BROWSING` | `x` | 選択中の項目、またはカーソル項目をカット対象として記録 |
| `BROWSING` | `p` | カレントディレクトリへ clipboard を貼り付け |
| `BROWSING` | `Esc` | フィルタ有効時はフィルタ解除、そうでなければ選択解除 |
| `BROWSING` | `/` | フィルタ入力開始 |
| `BROWSING` | `Delete` | 選択中の項目、またはカーソル項目をゴミ箱へ移動。複数対象時は確認ダイアログを表示 |
| `BROWSING` | `F2` | 単一対象のリネーム入力を開始 |
| `BROWSING` | `:` | コマンドパレットを開く |
| `FILTER` | 文字キー | フィルタ文字列を更新 |
| `FILTER` | `Backspace` | フィルタ文字列を 1 文字削除 |
| `FILTER` | `Enter` / `↓` | フィルタを確定して `BROWSING` に戻る |
| `FILTER` | `Esc` | フィルタを解除して `BROWSING` に戻る |
| `PALETTE` | 文字キー | コマンド名の絞り込みを更新 |
| `PALETTE` | `↑` / `↓` | コマンド候補を移動 |
| `PALETTE` | `Backspace` | 絞り込み文字列を 1 文字削除 |
| `PALETTE` | `Enter` | 選択中コマンドを実行 |
| `PALETTE` | `Esc` | コマンドパレットを閉じて `BROWSING` に戻る |
| `RENAME` / `CREATE` | 文字キー | 中央ペイン上部の入力ラインの値を更新 |
| `RENAME` / `CREATE` | `Backspace` | 中央ペイン上部の入力ラインの値を 1 文字削除 |
| `RENAME` / `CREATE` | `Enter` | リネームまたは新規作成を実行 |
| `RENAME` / `CREATE` | `Esc` | 入力をキャンセルして `BROWSING` に戻る |
| `CONFIRM` | `o` / `s` / `r` / `Esc` | 競合ダイアログで overwrite / skip / rename / cancel を選ぶ |
| `CONFIRM` | `Enter` / `Esc` | 削除確認ダイアログで confirm / cancel を選ぶ |
| `BUSY` | 任意 | 入力を無視し、ステータスバーへ警告を表示 |

選択はカレントディレクトリ単位で管理します。別ディレクトリへ移動した場合は選択を解除し、同じディレクトリの再読み込みではまだ存在する選択だけを維持します。copy は clipboard を維持し、cut は貼り付けで 1 件以上成功した時点で clipboard を空にします。cut 中の項目は一覧上で dim 表示し、保留中の移動対象であることを見分けられるようにしています。

貼り付け先に同名項目がある場合は競合ダイアログを表示し、MVP では選択した方針を残りの競合にも一括適用します。競合ダイアログ内には現在の競合メッセージと `overwrite` / `skip` / `rename` / `cancel` の操作ヒントをまとめて表示し、視線移動なしで判断できるようにしています。削除は OS のゴミ箱移動で実行し、複数対象時のみ確認ダイアログを挟みます。rename と新規作成はコマンド実行後に `Current Directory` 直下の入力ラインで編集し、filter も同じ位置でクエリを確認できます。filter 入力中は `Enter` または `↓` で一覧操作へ戻れ、確定後も入力ラインにクエリを残したまま `Esc` で即時解除できます。`items / selected / sort` の要約はその入力ラインの直上に固定表示されるため、中央ペインの状態を視線移動なしで確認できます。隠しファイルの表示切り替えもコマンドパレットから行い、3 ペインと一覧件数に即時反映されます。コマンドパレットにはショートカット付きの候補を表示し、未実装または条件不一致の候補は dim 表示します。通常の 1 行ヘルプには `s` / `d` / `F2` / `:` を表示します。ソート表示は中央ペイン上部の要約行で `name asc dirs:on` の形式で示します。ソート変更後は同じ項目が可視である限り中央ペインのカーソル位置を維持します。親・子ペインの並び順は固定の名前順とし、中央ペインの sort 変更では動かしません。バリデーションや重複名エラー時は入力値を保持したまま下段ステータスバーにエラー通知を表示します。

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
