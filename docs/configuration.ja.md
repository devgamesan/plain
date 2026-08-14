# 設定ファイル

zivo は起動時にユーザー設定用の `config.toml` を読み込みます。ファイルがまだ存在しない場合は、既定値入りの設定ファイルを自動生成します。

`config.toml` の場所は OS ごとに異なります。

- Linux: `${XDG_CONFIG_HOME:-~/.config}/zivo/config.toml`
- macOS: `~/Library/Application Support/zivo/config.toml`
- Windows: `%APPDATA%\\zivo\\config.toml`

> 想定読者: 起動時の既定値や高度なリソース上限を変更したい利用者。

## Config Editor の対象範囲

アプリ内の Config Editor は、頻繁に変更する基本設定に限定しています。

- ターミナル／GUI エディタのプリセット
- テーマと隠しファイル表示
- テキスト・画像・PDF・Office プレビューの有効化
- 既定のソート項目、順序、ディレクトリ優先
- 削除確認

Config Editor で `e` を押すと `config.toml` を開き、高度設定を編集できます。プレビュー詳細とresource limit、terminal templates、貼り付け動作、logging、file search の上限、background command の制限、custom actions、将来追加される設定はここで管理します。UI で基本設定を保存しても、高度設定・未知の設定・独自の TOML 値は保持されます。

Config Editor に未保存の変更がある場合は、先に保存または画面を閉じてから `e` で高度設定を開きます。外部エディタを閉じると `config.toml` を再読込し、変更を実行中の zivo と Config Editor に反映します。TOML の構文が不正な場合は現在の有効設定を維持して警告を表示します。設定によっては再起動が必要です。

`[terminal]` セクションにあるのは OS 別の起動コマンドテンプレート（`linux`、`macos`、`windows`）だけです。`launch_mode` という設定はありません。外部ターミナルを開くときは、設定済みテンプレート、またはプラットフォーム別の組み込みフォールバックを使用します。

## 設定項目一覧

| セクション | キー | 値 | 説明 |
| --- | --- | --- | --- |
| `terminal` | `linux` | shell 形式コマンド文字列の配列 | Linux 向けの任意ターミナル起動コマンドです。作業ディレクトリは `{path}` で埋め込みます。空文字や不正なエントリは無視されます。 |
| `terminal` | `macos` | shell 形式コマンド文字列の配列 | macOS 向けの任意ターミナル起動コマンドです。検証ルールは Linux と同じです。 |
| `terminal` | `windows` | shell 形式コマンド文字列の配列 | Windows / WSL 向けの任意ターミナル起動コマンドです。 |
| `editor` | `command` | shell 形式の文字列。例: `nvim -u NONE` | `Edit with terminal editor`（`e`）で起動するターミナルエディタです。ファイルパスは自動で末尾に付与されるため、設定値には含めません。GUI エディタや不正なコマンドは無視されます。 |
| `gui_editor` | `command` | shell 形式のコマンドテンプレート | `Edit with GUI editor` で行・列情報がある場合に使う GUI エディタ起動コマンドです。`{path}`、`{line}`、`{column}` を利用できます。既定値は `code --goto {path}:{line}:{column}` です。Config 画面では VS Code、VSCodium、Cursor、Sublime Text、Zed、JetBrains IDEA、PyCharm、WebStorm、Kate のプリセットへ切り替えられます。 |
| `gui_editor` | `fallback_command` | shell 形式のコマンドテンプレート | `Edit with GUI editor` で位置情報なしのパスを開く場合、または `command` が失敗した場合に使う GUI エディタ起動コマンドです。`{path}` を利用できます。既定値は `code {path}` です。任意の raw テンプレートは保持され、Config 画面では custom として表示されます。現在ディレクトリを GUI エディタで開くには custom action を使用します。 |
| `display` | `show_hidden_files` | `true` / `false` | 起動時の隠しファイル表示状態です。 |
| `display` | `show_directory_sizes` | `true` / `false` | ペイン内に再帰ディレクトリサイズを表示します。既定値は `true` です。大きいディレクトリでは計算コストがかかる場合があります。中央ペインを `size` ソートしている間は、この設定が `false` でも自動計算されます。 |
| `display` | `enable_text_preview` | `true` / `false` | 右ペインのテキストファイルプレビューを表示します。既定値は `true` です。grep 結果のコンテキストプレビューも同じ設定に従います。 |
| `display` | `enable_image_preview` | `true` / `false` | `chafa` を使った画像プレビューを右ペインで表示します。既定値は `true` です。`chafa` が未導入の場合は失敗ではなく依存不足メッセージを表示します。`image_preview_mode` を `kitty` にすると、対応端末で高精細な画像表示が可能です。 |
| `display` | `image_preview_mode` | `auto` / `kitty` / `chafa` | 画像プレビュー方式を選択します。既定値は `auto` です。`auto` では端末を自動検出し、Kitty/Ghostty 等の対応端末では Kitty graphics protocol、非対応端末では chafa Unicode 記号を使います。`kitty` は強制的に Kitty graphics protocol を使用します（対応端末必須）。`chafa` は従来の Unicode 記号出力を使用します。 |
| `display` | `enable_pdf_preview` | `true` / `false` | `pypdf` による上限制付き組み込み PDF テキスト抽出と、完了した抽出失敗時の任意 `pdftotext` fallback を有効にします。既定値は `true` です。無効時は設定無効であること、概要メタデータ、`Edit config` を表示します。 |
| `display` | `enable_office_preview` | `true` / `false` | 組み込み OOXML テキスト抽出による `docx` / `xlsx` / `pptx` のプレビューを有効にします。既定値は `true` です。無効時は設定無効であること、概要メタデータ、`Edit config` を表示します。 |
| `display` | `show_help_bar` | `true` / `false` | 画面下部のヘルプバーを表示します。既定値は `true` です。コマンドパレットが開いている場合は、この設定に関係なく常に表示されます。 |
| `display` | `theme` | 任意の組み込み Textual テーマ（例: `textual-dark`、`textual-light`、`dracula`、`tokyo-night`） | 起動時の UI テーマです。設定エディタでは変更内容が即座にプレビューされ、`s` で保存するとこの値が永続化されます。 |
| `display` | `preview_syntax_theme` | `auto` またはサポートされている Pygments style（例: `one-dark`、`xcode`、`nord`、`gruvbox-dark`） | 右ペインのテキストプレビューに使うシンタックスハイライト配色です。`auto` を選ぶと、現在の light/dark に応じた既定配色を使います。設定エディタで右ペインにテキストプレビューが出ている場合は、その場で即時プレビューされます。 |
| `display` | `preview_max_kib` | `64` / `128` / `256` / `512` / `1024` | 右ペインのファイルプレビューとプレビューサンプリングで読み込む最大量です。既定値は `64` です。大きな値にするとより深くプレビューできますが、I/O コストが増加します。 |
| `preview` | `timeout_seconds` / `image_timeout_seconds` | 0より大きい数値 | テキスト・PDF converter、組み込み Office 抽出、画像プレビューの最大処理時間（秒）です。既定値は `5` / `15` です。 |
| `preview` | `stdout_max_kib` / `stderr_max_kib` | 1以上の整数 | テキスト・PDF converter の stdout / stderr 保持上限（KiB）です。既定値は `256` / `16` です。 |
| `preview` | `image_stdout_max_mib` / `kitty_stdout_max_mib` | 1以上の整数 | chafa symbols / Kitty graphics protocol の出力保持上限（MiB）です。既定値は `2` / `32` です。 |
| `preview` | `input_max_mib` | 1以上の整数 | preview backend が処理する入力ファイルの上限（MiB）です。 |
| `preview` | `max_archive_entries` / `max_archive_entry_mib` / `max_archive_total_mib` | 1以上の整数 | Office ZIP の entry 数・各entry展開量・合計展開量の上限です。 |
| `preview` | `max_archive_compression_ratio` | 1以上の数値 | Office ZIP の圧縮率上限です。 |
| `preview` | `timeout_cache_seconds` | 0以上の数値 | timeout結果を再利用する秒数です。`0` で再利用しません。 |
| `display` | `default_sort_field` | `name` / `modified` / `size` | 中央ペインの初期ソート項目です。`name` は自然順（数値部分を値で比較、例: `file2` が `file10` より先）で並び替えます。 |
| `display` | `default_sort_descending` | `true` / `false` | `true` のとき、起動時のソートを降順にします。 |
| `display` | `directories_first` | `true` / `false` | 中央ペインでディレクトリをファイルより先にまとめて表示します。 |
| `display` | `grep_preview_context_lines` | 0 以上の整数 | grep 一致箇所の前後に表示するコンテキスト行数です。既定値は `3` です。 |
| `display` | `preview_word_wrap` | `true` / `false` | テキスト／grep プレビューの長い行を折り返します。既定値は `false` です。 |
| `behavior` | `confirm_delete` | `true` / `false` | ゴミ箱削除の前に確認ダイアログを表示します。`D` / `Shift+Delete` による完全削除は常に確認します。 |
| `behavior` | `confirm_exit` | `true` / `false` | zivo を終了するときに確認します。既定値は `true` です。 |
| `behavior` | `paste_conflict_action` | `prompt` / `overwrite` / `skip` / `rename` | 貼り付け競合時の既定動作です。`prompt` の場合は競合ダイアログを維持します。 |
| `logging` | `enabled` | `true` / `false` | 起動失敗や未処理例外をログファイルへ出力するかどうかを切り替えます。 |
| `logging` | `level` | `DEBUG` / `INFO` / `WARNING` / `ERROR` / `CRITICAL` | ログファイルへ出力するログレベルです。既定値は `ERROR` です。設定の反映にはアプリの再起動が必要です。 |
| `logging` | `path` | パス文字列 | 任意のログファイル保存先です。空文字なら `config.toml` と同じディレクトリの `zivo.log` を使います。ログファイルの既定の場所: Linux: `~/.config/zivo/zivo.log`、macOS: `~/Library/Application Support/zivo/zivo.log`。 |
| `bookmarks` | `paths` | 絶対パス文字列の配列 | `b` や Go の `@bookmark` フィルターで表示するブックマーク一覧です。重複パスは読み込み時に取り除かれます。 |
| `file_search` | `max_results` | 0以上の整数または省略 | 直接 Find file の最大結果件数です。キーを省略すると既定値1,000件、`0` では結果を無効にします。上限超過時はパレットに省略結果を明示します。 |
| `grep_search` | `max_results` | 0以上の整数または省略 | 直接 Grep search の最大結果件数です。キーを省略すると既定値1,000件、`0` では結果を無効にします。上限超過時はパレットに省略結果を明示します。 |
| `background_commands` | `max_output_kib` | `1`〜`4096`の整数 | `!` commandと`background` custom actionで保持するstdout/stderrそれぞれの最大量です。既定値はstreamごとに`1024` KiBです。超過時は先頭と末尾を保持し、中間を省略します。 |
| `background_commands` | `timeout_seconds` | `1`〜`86400`の整数 | `!` commandと`background` custom actionの最大実行時間です。既定値は`300`秒です。interactiveなterminal modeには適用しません。 |
| `actions` | `custom` | action table の配列 | コマンドパレットに表示するカスタムアクションです。詳しくは [カスタムアクション](custom-actions.ja.md) を参照してください。 |

## 設定例

```toml
[terminal]
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
grep_preview_context_lines = 3
preview_word_wrap = false

[preview]
timeout_seconds = 5
stdout_max_kib = 256
stderr_max_kib = 16
image_timeout_seconds = 15
image_stdout_max_mib = 2
kitty_stdout_max_mib = 32
input_max_mib = 256
max_archive_entries = 4096
max_archive_entry_mib = 64
max_archive_total_mib = 256
max_archive_compression_ratio = 100
timeout_cache_seconds = 1

[behavior]
confirm_delete = true
confirm_exit = true
paste_conflict_action = "prompt"

[file_search]
# 空欄の場合は結果数を1,000件に制限します。
# max_results = 1000

[grep_search]
# 空欄の場合は結果数を制限しません（既定値）。
# max_results = 1000

[background_commands]
max_output_kib = 1024
timeout_seconds = 300

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
- ヘルプバーの文言は現在の UI 状態と zivo 標準キーマップに追随します。以前の `[help_bar]` セクションは互換性のため無視され、次回設定を保存したときに削除されます。
