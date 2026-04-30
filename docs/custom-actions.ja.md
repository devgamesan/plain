# カスタムアクション

カスタムアクションは、`config.toml` からコマンドパレット項目を追加する仕組みです。formatter、checker、画像最適化、archive 作成、`lazygit` のような terminal app への接続に使えます。

## 設定

`config.toml` に `[[actions.custom]]` テーブルを追加します。

```toml
[[actions.custom]]
name = "Optimize PNG"
command = ["oxipng", "-o", "4", "{file}"]
when = "single_file"
mode = "background"
extensions = ["png"]

[[actions.custom]]
name = "Create tar.gz from selection"
command = ["tar", "-czf", "{cwd_basename}.tar.gz", "{selection}"]
when = "selection"
mode = "background"

[[actions.custom]]
name = "Open lazygit"
command = ["lazygit"]
when = "always"
mode = "terminal"
cwd = "{cwd}"

[[actions.custom]]
name = "Open lazygit in new window"
command = ["lazygit"]
when = "always"
mode = "terminal_window"
cwd = "{cwd}"
```

## フィールド

| フィールド | 必須 | 説明 |
| --- | --- | --- |
| `name` | yes | コマンドパレットに表示する名前。 |
| `command` | yes | 実行する argv 配列。shell 経由では実行しません。 |
| `when` | no | `always`、`single_file`、`selection`。既定値は `always`。 |
| `mode` | no | `background` または `terminal`。既定値は `background`。 |
| `cwd` | no | 作業ディレクトリのテンプレート。既定値は `{cwd}`。 |
| `extensions` | no | `single_file` 用の拡張子条件。先頭の dot はあってもなくても構いません。 |

## mode の使い分け

`background` は非対話コマンド向けです。zivo は stdout/stderr を捕捉し、成功/失敗を status bar に表示します。TTY が必要な TUI app には使わないでください。

`terminal` は `lazygit` のような TUI/対話コマンド向けです。zivo の画面を一時停止し、現在の terminal でコマンドを実行し、終了後に zivo へ戻ります。

`terminal_window` は、新しいターミナルウィンドウまたはタブでコマンドを実行します。zivo は suspend せず、新しいウィンドウは独立して実行され、コマンド完了後にシェルプロンプトが表示されます。zivo と並行して使いたいツールに便利です。

## 変数

| 変数 | 説明 |
| --- | --- |
| `{cwd}` | zivo の current directory。 |
| `{cwd_basename}` | `{cwd}` の basename。 |
| `{file}` | フォーカス中の単一ファイルパス。`single_file` 向け。 |
| `{name}` | フォーカス中ファイルの basename。 |
| `{stem}` | フォーカス中ファイル名から拡張子を除いた名前。 |
| `{ext}` | フォーカス中ファイルの拡張子。先頭の dot は含みません。 |
| `{selection}` | 選択パス。複数の argv 要素として展開されます。 |

`{selection}` は `command` 配列内で単独の要素にしてください。`"{selection}"` は有効ですが、`"files={selection}"` は拒否されます。

## 安全性

カスタムアクション実行前に、展開後の command、cwd、mode を確認します。destructive なコマンドかどうかは自動判定しないため、破壊的な操作は名前を明確にし、コマンド側でも確認を挟む運用にしてください。
