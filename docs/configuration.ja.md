# 設定ファイル

zivo は起動時にユーザー設定用の `config.toml` を読み込みます。ファイルがまだ存在しない場合は、既定値入りの設定ファイルを自動生成します。

`config.toml` の場所は OS ごとに異なります。

- Linux: `${XDG_CONFIG_HOME:-~/.config}/zivo/config.toml`
- macOS: `~/Library/Application Support/zivo/config.toml`
- Windows: `%APPDATA%\\zivo\\config.toml`

## 設定項目一覧

| セクション | キー | 値 | 説明 |
| --- | --- | --- | --- |
| `terminal` | `linux` | shell 形式コマンド文字列の配列 | Linux 向けの任意ターミナル起動コマンドです。作業ディレクトリは `{path}` で埋め込みます。空文字や不正なエントリは無視されます。 |
| `terminal` | `macos` | shell 形式コマンド文字列の配列 | macOS 向けの任意ターミナル起動コマンドです。検証ルールは Linux と同じです。 |
| `terminal` | `windows` | shell 形式コマンド文字列の配列 | Windows / WSL 向けの任意ターミナル起動コマンドです。 |
| `editor` | `command` | shell 形式の文字列。例: `nvim -u NONE` | `e` で起動するターミナルエディタです。ファイルパスは自動で末尾に付与されるため、設定値には含めません。GUI エディタや不正なコマンドは無視されます。 |
| `gui_editor` | `command` | shell 形式のコマンドテンプレート | 行・列情報がある場合に使う GUI エディタ起動コマンドです。`{path}`、`{line}`、`{column}` を利用できます。既定値は `code --goto {path}:{line}:{column}` です。Config 画面では VS Code、VSCodium、Cursor、Sublime Text、Zed、JetBrains IDEA、PyCharm、WebStorm、Kate のプリセットへ切り替えられます。 |
| `gui_editor` | `fallback_command` | shell 形式のコマンドテンプレート | 位置情報なしでパスを開く場合、または `command` が失敗した場合に使う GUI エディタ起動コマンドです。`{path}` を利用できます。既定値は `code {path}` です。任意の raw テンプレートは保持され、Config 画面では custom として表示されます。 |
| `display` | `show_hidden_files` | `true` / `false` | 起動時の隠しファイル表示状態です。 |
| `display` | `show_directory_sizes` | `true` / `false` | ペイン内に再帰ディレクトリサイズを表示します。既定値は `true` です。大きいディレクトリでは計算コストがかかる場合があります。中央ペインを `size` ソートしている間は、この設定が `false` でも自動計算されます。 |
| `display` | `enable_text_preview` | `true` / `false` | 右ペインのテキストファイルプレビューを表示します。既定値は `true` です。grep 結果のコンテキストプレビューも同じ設定に従います。 |
| `display` | `enable_image_preview` | `true` / `false` | `chafa` を使った画像プレビューを右ペインで表示します。既定値は `true` です。`chafa` が未導入の場合は失敗ではなく依存不足メッセージを表示します。`image_preview_mode` を `kitty` にすると、対応端末で高精細な画像表示が可能です。 |
| `display` | `image_preview_mode` | `auto` / `kitty` / `chafa` | 画像プレビュー方式を選択します。既定値は `auto` です。`auto` では端末を自動検出し、Kitty/Ghostty 等の対応端末では Kitty graphics protocol、非対応端末では chafa Unicode 記号を使います。`kitty` は強制的に Kitty graphics protocol を使用します（対応端末必須）。`chafa` は従来の Unicode 記号出力を使用します。 |
| `display` | `enable_pdf_preview` | `true` / `false` | `pdftotext` を使った PDF プレビューを有効にします。既定値は `true` です。無効にすると PDF は通常の非対応メッセージへ戻ります。 |
| `display` | `enable_office_preview` | `true` / `false` | `docx` / `xlsx` / `pptx` のプレビューを `pandoc` 変換で有効にします。既定値は `true` です。無効にすると、これらの形式は通常の非対応メッセージへ戻ります。 |
| `display` | `show_help_bar` | `true` / `false` | 画面下部のヘルプバーを表示します。既定値は `true` です。コマンドパレットが開いている場合は、この設定に関係なく常に表示されます。 |
| `display` | `theme` | 任意の組み込み Textual テーマ（例: `textual-dark`、`textual-light`、`dracula`、`tokyo-night`） | 起動時の UI テーマです。設定エディタでは変更内容が即座にプレビューされ、`s` で保存するとこの値が永続化されます。 |
| `display` | `preview_syntax_theme` | `auto` またはサポートされている Pygments style（例: `one-dark`、`xcode`、`nord`、`gruvbox-dark`） | 右ペインのテキストプレビューに使うシンタックスハイライト配色です。`auto` を選ぶと、現在の light/dark に応じた既定配色を使います。設定エディタで右ペインにテキストプレビューが出ている場合は、その場で即時プレビューされます。 |
| `display` | `preview_max_kib` | `64` / `128` / `256` / `512` / `1024` | 右ペインのファイルプレビューとプレビューサンプリングで読み込む最大量です。既定値は `64` です。大きな値にするとより深くプレビューできますが、I/O コストが増加します。 |
| `display` | `default_sort_field` | `name` / `modified` / `size` | 中央ペインの初期ソート項目です。 |
| `display` | `default_sort_descending` | `true` / `false` | `true` のとき、起動時のソートを降順にします。 |
| `display` | `directories_first` | `true` / `false` | 中央ペインでディレクトリをファイルより先にまとめて表示します。 |
| `behavior` | `confirm_delete` | `true` / `false` | ゴミ箱削除の前に確認ダイアログを表示します。`D` / `Shift+Delete` による完全削除は常に確認します。 |
| `behavior` | `paste_conflict_action` | `prompt` / `overwrite` / `skip` / `rename` | 貼り付け競合時の既定動作です。`prompt` の場合は競合ダイアログを維持します。 |
| `logging` | `enabled` | `true` / `false` | 起動失敗や未処理例外をログファイルへ出力するかどうかを切り替えます。 |
| `logging` | `level` | `DEBUG` / `INFO` / `WARNING` / `ERROR` / `CRITICAL` | ログファイルへ出力するログレベルです。既定値は `ERROR` です。設定の反映にはアプリの再起動が必要です。 |
| `logging` | `path` | パス文字列 | 任意のログファイル保存先です。空文字なら `config.toml` と同じディレクトリの `zivo.log` を使います。ログファイルの既定の場所: Linux: `~/.config/zivo/zivo.log`、macOS: `~/Library/Application Support/zivo/zivo.log`。 |
| `bookmarks` | `paths` | 絶対パス文字列の配列 | `b` やコマンドパレットの `Show bookmarks` で使うブックマーク一覧です。重複パスは読み込み時に取り除かれます。 |
| `file_search` | `max_results` | 整数または空 | ファイル検索の最大結果件数です。空欄の場合は制限なし（既定値）。大規模リポジトリでのメモリ使用量を削減するために設定します。 |
| `actions` | `custom` | action table の配列 | コマンドパレットに表示するカスタムアクションです。詳しくは [カスタムアクション](custom-actions.ja.md) を参照してください。 |

## 設定例

```toml
[terminal]
launch_mode = "window"
linux = ["konsole --working-directory {path}", "gnome-terminal --working-directory={path}"]
macos = ["open -a Terminal {path}"]
windows = ["wt -d {path}"]

[editor]
command = "nvim -u NONE"

[gui_editor]
command = "code --goto {path}:{line}:{column}"
fallback_command = "code {path}"

[display]
show_hidden_files = false
show_directory_sizes = true
enable_text_preview = true
enable_image_preview = true
image_preview_mode = "auto"
enable_pdf_preview = true
enable_office_preview = true
show_help_bar = true
theme = "textual-dark"
preview_syntax_theme = "auto"
preview_max_kib = 64
default_sort_field = "name"
default_sort_descending = false
directories_first = true

[behavior]
confirm_delete = true
paste_conflict_action = "prompt"

[logging]
enabled = true
level = "ERROR"
path = ""

[bookmarks]
paths = ["/home/user/src", "/home/user/docs"]
```

## 補足

- 設定値が不正でも起動は止めず、該当項目だけ既定値へフォールバックして初回ロード後に警告を表示します。
- `logging.enabled = true` の場合、起動失敗や未処理例外は後から調査できるように指定ログファイルへ追記されます。
- 受け入れ可能な `display.theme` の値は、インストールされている Textual のバージョンに同梱される組み込みテーマに依存します。
- 受け入れ可能な `display.preview_syntax_theme` の値は、インストール環境で利用可能な Pygments スタイルに依存します。
