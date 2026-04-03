# Peneo

[English README](README.md)

Peneo は、ターミナルで作業しながら GUI アプリとも自然に行き来したい環境向けの、Textual ベースの TUI ファイルマネージャです。親 / 現在 / 子ディレクトリを並べた 3 ペイン構成で、GUI のファイラーに近い感覚で主要操作へたどり着けることを重視しています。よく使う操作は画面上のヘルプに常時表示され、Peneo 上の操作から各種ファイルを OS の既定アプリで開けます。

## 特徴

- 親 / 現在 / 子ディレクトリを並べたシンプルな 3 ペイン表示です。ディレクトリ移動、複数選択、コピー、カット、貼り付け、ゴミ箱削除、リネーム、新規作成、対応アーカイブの展開をキーボードだけで操作できます。
  ![](docs/resources/screen-entire-screen.png)
  _3 ペインで周辺階層を見比べながら、現在ディレクトリの内容を操作している状態です。_
- よく使う操作は画面上のヘルプに常時表示されるため、操作方法に迷いにくくしています。
  ![](docs/resources/screen-help-bar.png)
  _画面下部のヘルプバーに、現在使える主要キーを常時表示している状態です。_
- 使用頻度の低い操作はコマンドパレットに集約しています。
  ![](docs/resources/screen-command-palette.png)
  _`:` でコマンドパレットを開き、主要コマンドへアクセスしている状態です。_
- 3 ペインの下に埋め込み split terminal を開けます。`Ctrl+T` でブラウザとターミナルをすばやく切り替えられます。
  ![](docs/resources/screen-split-terminal.png)
  _`Ctrl+T` で埋め込み split terminal を開き、上段のブラウザ 3 ペインを保ったまま下段のシェル出力を確認している状態です。_
- フィルタ入力、再帰ファイル検索、再帰 grep 検索、ディレクトリ合計サイズ表示、ソート切り替えをサポートしています。
  ![](docs/resources/screen-filter.png)
  _`/` でフィルタ入力を開き、現在ディレクトリの内容をその場で絞り込んでいる状態です。_
  ![](docs/resources/screen-find-command.png)
  _`Ctrl+F` で `Find file` を開き、現在ディレクトリ配下を再帰的に検索している状態です。_
- ファイルやディレクトリの属性も確認できます。
  ![](docs/resources/screen-attributes.png)
  _属性ダイアログで、パス、サイズ、更新日時、権限などを確認している状態です。_
- ファイルは OS の既定アプリで開けます。現在ディレクトリは OS のファイルマネージャや外部ターミナルへ引き渡せて、必要なら `e` で現在のターミナル内エディタも起動できます。
  ![](docs/resources/screen-open.png)
  _ファイルを既定アプリで開いたり、現在ディレクトリを外部アプリへ渡したりできる操作を示しています。_


## インストール

`uv` が入っている環境で、リポジトリを clone してからツールとしてインストールします。

```bash
git clone https://github.com/devgamesan/peneo.git
cd peneo
uv tool install --from . peneo
```

### 依存ツール

一部の機能は `PATH` 上で外部コマンドが利用可能であることを前提としています：

**grep 検索 (`Ctrl+G`) に必要：**
- `ripgrep` (`rg`)

**パスコピーに必要：**
- Linux: `xclip` または `wl-copy` (Wayland)
- macOS: `pbcopy` (macOS に含まれています)
- WSL: `clip.exe` (WSL に含まれています)、または上記の Linux コマンド

**WSL で推奨：**
- `wslu` (ブリッジコマンド `wslview` など)

Ubuntu / Debian 系でのインストール例：

```bash
# grep 検索とパスコピー用
sudo apt install ripgrep xclip

# WSL の場合（推奨）
sudo apt install wslu
```

更新時は最新を pull したあとに同じコマンドを再実行してください。

## 起動

```bash
peneo
```

開発中にローカル checkout から直接起動したい場合は、リポジトリ直下で次を使えます。

```bash
uv run peneo
```

`peneo` 本体は親シェルのカレントディレクトリを直接変更できません。終了時に Peneo で最後に開いていたディレクトリへシェル側も移動したい場合は、まず次の 1 行を `.bashrc` や `.zshrc` に追加してください。

```bash
eval "$(peneo init bash)"  # bash の場合
eval "$(peneo init zsh)"   # zsh の場合
```

新しいシェルを開くか、現在のシェルでも同じ行を 1 回実行するとすぐ有効になります。これで `peneo-cd` というシェル関数が定義されます。以後、その挙動が必要なときだけ通常の `peneo` の代わりに次を使います。

```bash
peneo-cd
```

この挙動が不要なら、通常どおり `peneo` / `uv run peneo` を使えます。

ファイルにカーソルを合わせた状態で `e` を押すと、現在のターミナル上でターミナルエディタへ切り替えられます。`config.toml` の `editor.command` が設定されていればそれを優先し、未設定なら `$EDITOR`、さらに `nvim`、`vim`、`nano` などの組み込み候補へフォールバックします。

## 設定ファイル

Peneo は起動時にユーザー設定用の `config.toml` を読み込みます。ファイルがまだ存在しない場合は、既定値入りの設定ファイルを自動生成します。

- Linux: `${XDG_CONFIG_HOME:-~/.config}/peneo/config.toml`
- macOS: `~/Library/Application Support/peneo/config.toml`
- Windows 向けの設定パスも予約していますが、Windows ネイティブ実行自体は引き続き非対応です

設定できる項目は次のとおりです。

| セクション | キー | 値 | 説明 |
| --- | --- | --- | --- |
| `terminal` | `linux` | shell 形式コマンド文字列の配列 | Linux 向けの任意ターミナル起動コマンドです。作業ディレクトリは `{path}` で埋め込みます。空文字や不正なエントリは無視されます。 |
| `terminal` | `macos` | shell 形式コマンド文字列の配列 | macOS 向けの任意ターミナル起動コマンドです。検証ルールは Linux と同じです。 |
| `terminal` | `windows` | shell 形式コマンド文字列の配列 | Windows / WSL ブリッジ向けの任意ターミナル起動コマンドです。Windows ネイティブ実行は未対応ですが設定キー自体は受け付けます。 |
| `editor` | `command` | shell 形式の文字列。例: `nvim -u NONE` | `e` で起動するターミナルエディタです。ファイルパスは自動で末尾に付与されるため、設定値には含めません。GUI エディタや不正なコマンドは無視されます。 |
| `display` | `show_hidden_files` | `true` / `false` | 起動時の隠しファイル表示状態です。 |
| `display` | `show_directory_sizes` | `true` / `false` | ペイン内に再帰ディレクトリサイズを表示します。大きいディレクトリでは計算コストがあるため既定値は `false` です。中央ペインを `size` ソートしている間は、この設定が `false` でも自動計算されます。 |
| `display` | `theme` | `textual-dark` / `textual-light` | 起動時の UI テーマです。設定エディタから保存した場合もこの値が使われます。 |
| `display` | `default_sort_field` | `name` / `modified` / `size` | 中央ペインの初期ソート項目です。 |
| `display` | `default_sort_descending` | `true` / `false` | `true` のとき、起動時のソートを降順にします。 |
| `display` | `directories_first` | `true` / `false` | 中央ペインでディレクトリをファイルより先にまとめて表示します。 |
| `behavior` | `confirm_delete` | `true` / `false` | ゴミ箱削除の前に確認ダイアログを表示します。 |
| `behavior` | `paste_conflict_action` | `prompt` / `overwrite` / `skip` / `rename` | 貼り付け競合時の既定動作です。`prompt` の場合は競合ダイアログを維持します。 |

例:

```toml
[terminal]
linux = ["konsole --working-directory {path}", "gnome-terminal --working-directory={path}"]
macos = ["open -a Terminal {path}"]
windows = ["wt -d {path}"]

[editor]
command = "nvim -u NONE"

[display]
show_hidden_files = false
show_directory_sizes = false
theme = "textual-dark"
default_sort_field = "name"
default_sort_descending = false
directories_first = true

[behavior]
confirm_delete = true
paste_conflict_action = "prompt"
```

設定値が不正でも起動は止めず、該当項目だけ既定値へフォールバックして初回ロード後に警告を表示します。

## 基本操作

主要キーは次のとおりです。

| 状態 | キー | 動作 |
| --- | --- | --- |
| 通常時 | `↑` / `k` | カーソル移動 |
| 通常時 | `↓` / `j` | カーソル移動 |
| 通常時 | `←` / `h` / `Backspace` | 親ディレクトリへ移動 |
| 通常時 | `→` / `l` | ディレクトリなら入る |
| 通常時 | `Alt+←` | 履歴を一つ戻る |
| 通常時 | `Alt+→` | 履歴を一つ進む |
| 通常時 | `Ctrl+J` | 特定のパスへ移動するための入力を開く |
| 通常時 | `Alt+Home` | ホームディレクトリへ移動 |
| 通常時 | `Ctrl+O` | ディレクトリ履歴リストを開き、選択したディレクトリへ移動 |
| 通常時 | `Ctrl+B` | ブックマークリストを開き、選択したディレクトリへ移動 |
| 通常時 | `Enter` | ディレクトリなら入る、ファイルなら既定アプリで開く |
| 通常時 | `e` | カーソル中のファイルを `editor.command` -> `$EDITOR` -> 組み込み既定値の順でターミナルエディタで開く |
| 通常時 | `i` | 単一対象の属性ダイアログを開く |
| 通常時 | `F5` | 現在ディレクトリを再読み込み |
| 通常時 | `Space` | 選択トグル後に次行へ移動 |
| 通常時 | `Ctrl+A` | 現在ディレクトリで表示中の項目をすべて選択 |
| 通常時 | `y` | 選択中の項目、またはカーソル項目をコピー対象にする |
| 通常時 | `x` | 選択中の項目、またはカーソル項目をカット対象にする |
| 通常時 | `p` | 現在ディレクトリへ貼り付け |
| 通常時 | `c` | 選択中のパス一覧、またはカーソル中のパスをシステムクリップボードへコピー |
| 通常時 | `Delete` | 選択中の項目、またはカーソル項目をゴミ箱へ移動（既定では確認あり、設定で変更可能） |
| 通常時 | `F2` | 単一対象のリネーム入力を開始 |
| 通常時 | `b` | 現在ディレクトリのブックマーク追加/削除を切り替える |
| 通常時 | `.` | 隠しファイル表示を切り替える |
| 通常時 | `/` | フィルタ入力を開始 |
| 通常時 | `s` | ソート順を循環切り替え |
| 通常時 | `d` | ディレクトリ優先表示を切り替え |
| 通常時 | `q` | アプリを終了 |
| 通常時 | `Esc` | フィルタ有効時はフィルタ解除、そうでなければ選択解除 |
| 通常時 | `:` | コマンドパレットを開く |
| 通常時 | `Ctrl+F` | 再帰ファイル検索を開く |
| 通常時 | `Ctrl+G` | 再帰 grep 検索を開く（`ripgrep` / `rg` が `PATH` 上に必要） |
| 通常時 | `Ctrl+T` | 埋め込み split terminal を開閉する |
| 通常時（split terminal 表示中） | 文字入力やブラウザ操作キー | split terminal が入力を持つ間は無効 |
| フィルタ入力中 | 文字入力 | フィルタ文字列を更新 |
| フィルタ入力中 | `Backspace` | 1 文字削除 |
| フィルタ入力中 | `Enter` / `↓` | フィルタを適用して一覧操作へ戻る |
| フィルタ入力中 | `Esc` | フィルタを解除する |
| コマンドパレット表示中 | 文字入力 / `↑` / `↓` / `k` / `j` / `Enter` / `Esc` | コマンドを絞り込み、選択、実行、キャンセル |
| split terminal フォーカス中 | 文字入力 / 矢印 / `Enter` / `Backspace` / `Tab` | 入力を埋め込みシェルへ送る |
| split terminal フォーカス中 | `Esc` | 埋め込み split terminal を閉じる |
| split terminal フォーカス中 | `Ctrl+T` | 埋め込み split terminal を閉じる |
| split terminal フォーカス中 | `Ctrl+V` | クリップボードの内容をターミナルに貼り付け |
| 名前入力中 | 文字入力 / `Backspace` / `Enter` / `Esc` | リネームや新規作成の入力値を編集、確定、キャンセル |
| 確認ダイアログ表示中 | `Enter` / `Esc` | 削除確認を確定 / 中止 |
| 確認ダイアログ表示中 | `o` / `s` / `r` / `Esc` | 貼り付け競合を overwrite / skip / rename / cancel |

`e` は GUI アプリを別ウィンドウで開くのではなく、現在のターミナルセッション内でターミナルエディタへ切り替える操作です。`editor.command` と `$EDITOR` の両方が設定されている場合は `editor.command` を優先します。

## コマンドパレット

使用頻度の低い操作は `:` で開くコマンドパレットにまとめています。現在使える主なコマンドは次のとおりです。

| コマンド | 表示条件 | 動作 / 補足 |
| --- | --- | --- |
| `Find files` | 常に表示 | 再帰ファイル検索を開きます。 |
| `Grep search` | 常に表示 | 再帰 grep 検索を開きます（`ripgrep` / `rg` が `PATH` 上に必要）。 |
| `History search` | 常に表示 | ディレクトリ履歴リストを開き、選択したディレクトリへ移動します。 |
| `Show bookmarks` | 常に表示 | 保存済みのブックマークリストを開き、選択したディレクトリへ移動します。 |
| `Go back` | ディレクトリ履歴に戻り先があるとき | 履歴を一つ戻ります。 |
| `Go forward` | ディレクトリ履歴に進み先があるとき | 履歴を一つ進みます。 |
| `Go to path` | 常に表示 | 特定のパスへ移動するための入力を開きます。 |
| `Go to home directory` | 常に表示 | ホームディレクトリへ移動します。 |
| `Reload directory` | 常に表示 | 現在ディレクトリを再読み込みします。 |
| `Toggle split terminal` | 常に表示 | 埋め込み split terminal を開閉します。 |
| `Show attributes` | 単一対象が選択中またはフォーカス中のとき | 読み取り専用の属性ダイアログを開きます。`i` でも実行できます。 |
| `Rename` | 単一対象が選択中またはフォーカス中のとき | 単一対象のリネーム入力を開始します。 |
| `Extract archive` | 単一の対応アーカイブファイルが選択中またはフォーカス中のとき | `.zip` / `.tar` / `.tar.gz` / `.tar.bz2` の展開を開始します。展開先入力は絶対パスと相対パスの両方に対応し、相対パスはアーカイブ親ディレクトリ基準で解決されます。初期値はアーカイブと同じ階層にある同名ディレクトリの絶対パスです。既存パスとの衝突がある場合は事前確認し、展開中は status bar に entry 件数ベースの進捗を表示します。 |
| `Open in editor` | 単一ファイルが選択中またはフォーカス中のとき | フォーカス中のファイルを `editor.command` -> `$EDITOR` -> 組み込み既定値の順でターミナルエディタで開きます。 |
| `Copy path` | 対象が 1 件以上あるとき | 選択中のパス一覧、または未選択時はフォーカス中のパスをシステムクリップボードへコピーします。`c` でも実行できます。 |
| `Move to trash` | 対象が 1 件以上あるとき | 選択中の項目、またはフォーカス項目をゴミ箱へ移動します（既定では確認あり、設定で変更可能）。 |
| `Open in file manager` | 常に表示 | 現在ディレクトリを OS のファイルマネージャで開きます。 |
| `Open terminal` | 常に表示 | `config.toml` の設定を優先しつつ、現在ディレクトリ起点で外部ターミナルを起動します。 |
| `Bookmark this directory` / `Remove bookmark` | 常に表示 | 現在ディレクトリを `[bookmarks].paths` に追加または削除します。ラベルは現在状態を反映し、`b` でも切り替えられます。 |
| `Show hidden files` / `Hide hidden files` | 常に表示 | ブラウザ 3 ペインの隠しファイル表示を切り替えます。ラベルは現在状態を反映し、`.` でも切り替えられます。 |
| `Edit config` | 常に表示 | 起動時設定を編集するオーバーレイを開きます。優先ターミナルエディタ、隠しファイル表示、ディレクトリサイズ表示、テーマ、ソート、貼り付け競合時の既定動作、削除確認の有無などを編集できます。`↑` / `↓` で項目移動、`←` / `→` / `Enter` で値変更、`s` で `config.toml` 保存、`e` で生の設定ファイルをターミナルエディタで開けます。 |
| `Create file` | 常に表示 | 現在ディレクトリで新規ファイル作成の入力を開始します。 |
| `Create directory` | 常に表示 | 現在ディレクトリで新規ディレクトリ作成の入力を開始します。 |

## 対応環境と注意

- 現時点で動作確認している OS は Ubuntu と WSL 上の Ubuntu です。
- 既定アプリ起動、ファイルマネージャ起動、ターミナル起動などの GUI 連携も主にその環境で確認しています。
- 埋め込み split terminal は現状 POSIX 環境、特に Ubuntu/Linux と WSL を前提にしています。
- 外部起動まわりは Linux、macOS、WSL を意識したフォールバックを持ちます。Windows ネイティブ実行はサポート対象外です。
- `config.toml` でターミナルエディタやターミナル起動コマンドを指定した場合は、その設定を組み込みフォールバックより優先します。
- WSL では、優先ブリッジ動作に使う `wslview` を利用できるよう `wslu` のインストールが必要です。
- WSL では `wslview`、`explorer.exe`、`clip.exe` のような Windows 側ブリッジを優先し、WSLg や Linux デスクトップ向けのフォールバックも維持します。
- 挙動やキーバインドは今後見直す可能性があります。
- ファイル操作は、選択したディレクトリエントリ自体に対して行われます。選択中の項目が symlink の場合も、リンク先を暗黙に辿って変更せず、symlink エントリ自体を操作します。

## 関連ドキュメント

- 実装構造: [docs/architecture.md](docs/architecture.md)
- MVP メモ: [docs/spec_mvp.md](docs/spec_mvp.md)
- 性能確認メモ: [docs/performance.md](docs/performance.md)

## 開発者向け

開発環境を作る場合は次を実行します。

```bash
uv sync --python 3.12 --dev
```

テストと静的検査:

```bash
uv run ruff check .
uv run pytest
```
