# コマンドパレット一覧

`:` で開くコマンドパレットで利用可能な全コマンドの一覧です。
属性表示、パスコピー、ブックマーク変更、パス移動、外部アプリ起動、履歴検索、再読み込みなどの低頻度操作は、単一キーではなくこのパレットから実行します。
Transferモードでは、アクティブな転送ペインで実行できるコマンドだけをコマンドパレットに表示します。
タブバーは 2 タブ以上開いている場合にだけ表示されます。

クエリが空の場合は、`Navigate`、`File`、`Search`、`View`、`System`、`Custom actions` の固定カテゴリを表示します。カテゴリ順とコマンド順位は決定的で、利用履歴やテレメトリは使用しません。

コマンド一覧全体はマウスホイールでスクロールできます。キーボードのカーソル移動（`↑` / `↓` または `Ctrl+j` / `Ctrl+k`）では、選択行が自動的に表示範囲へ追従します。

検索ではコマンドの keywords と一般的な別名にも一致します。ラベル完全一致、ラベル前方一致、単語前方一致、部分一致、決定的な fuzzy 一致の順で順位付けします。無効なコマンドも検索対象に残り、具体的な理由を表示します。無効項目で Enter を押すと実行せず同じ理由を warning で通知します。カスタムアクションは設定済みの context 条件を維持し、名前で検索できます。

| コマンド | 表示条件 | 動作 / 補足 |
| --- | --- | --- |
| `New tab` | 常に表示 | 現在ディレクトリを初期値にした新しいブラウズタブを開きます。 |
| `Next tab` | 2 タブ以上開いているとき | 次のブラウズタブへ切り替えます。 |
| `Previous tab` | 2 タブ以上開いているとき | 前のブラウズタブへ切り替えます。 |
| `Close current tab` | 2 タブ以上開いているとき | アクティブなブラウズタブを閉じます。最後の 1 タブは閉じられません。 |
| `Find files` | 常に表示 | 再帰ファイル検索を開きます。 |
| `Grep search` | 常に表示 | 共通の再帰コンテンツ検索を開きます（`ripgrep` / `rg` が `PATH` 上に必要）。従来の `search contents` も検索用 alias として利用できます。current directory / selected files/directories / Search Workspace（Search Workspace を開いているときだけ選択可能）の scope を選択でき、keyword / filename / include extension / exclude extension の各フィルタを共通で利用できます。選択したディレクトリは再帰的に検索します。 |
| `History search` | 常に表示 | ディレクトリ履歴リストを開き、選択したディレクトリへ移動します。 |
| `Show bookmarks` | 常に表示 | 保存済みのブックマークリストを開き、選択したディレクトリへ移動します。 |
| `Go back` | ディレクトリ履歴に戻り先があるとき | 履歴を一つ戻ります。 |
| `Go forward` | ディレクトリ履歴に進み先があるとき | 履歴を一つ進みます。 |
| `Go to path` | 常に表示 | 特定のパスへ移動するための入力を開き、一致するディレクトリ候補表示と `Tab` 補完を使えます。 |
| `Go to home directory` | 常に表示 | ホームディレクトリへ移動します。 |
| `Reload directory` | 常に表示 | 現在ディレクトリを再読み込みします。 |
| `Toggle transfer mode` / `Close transfer mode` | 常に表示 | 通常の 3 ペインブラウザと 2 ペイン転送レイアウトを切り替えます。 |
| `Undo last file operation` | Undo 履歴があるとき | 直前の Undo 対象リネーム、貼り付け、ゴミ箱移動を取り消します。 |
| `Select all` | 現在ディレクトリに表示中の項目が 1 件以上あるとき | 現在ディレクトリで表示中の項目をすべて選択します。 |
| `Save results` | grep 検索結果を表示中 | 現在の grep 結果を現在のディレクトリの `grep_results.txt` へ保存します。設定済みの grep プレビュー context 行を含み、既存ファイルは変更しません。 |
| `Replace text` | 常に表示 | Scope を選べる単一の置換パレットを開きます。初期 Scope は選択状態に応じて Selected files、Current file、Current directory になります。Current file、Selected files、Current directory、Found files、Grep result files を選択でき、利用できない Scope は理由を表示します。Find/Replace は常に表示し、再帰検索する Scope では filename と拡張子フィルターも表示します。右ペインに diff をプレビューしてから確認・適用します。 |
| `Show attributes` | 単一対象が選択中またはフォーカス中のとき | 読み取り専用の属性ダイアログを開きます。 |
| `Rename` | 単一対象が選択中またはフォーカス中のとき | 単一対象のリネーム入力を開始します。 |
| `Change permissions` | Linux / macOS / WSL の実ファイルシステム上の 1 件以上の対象が選択中またはフォーカス中のとき | 選択中の全対象、または未選択時はフォーカス対象の permission 変更入力を開始します。`755` や `644` のような 3 桁 octal mode を入力します。ダイアログには対象数・種別と、symlink をスキップしてリンク先を辿らない方針が表示されます。`Recursive` の既定値は `No` で、`Tab` により `Yes` を選ぶとディレクトリ配下にも適用します。検索ワークスペースと native Windows では表示しません。Windows は `chmod` 経由で POSIX permission bit を表現できないため対象外です。 |
| `Change owner` | Linux / macOS / WSL の実ファイルシステム上の 1 件以上の対象が選択中またはフォーカス中のとき | 選択中の全対象、または未選択時はフォーカス対象の owner/group 変更入力を開始します。`owner`、`owner:group`、`:group` を入力できます。ダイアログには対象数・種別と、symlink をスキップしてリンク先を辿らない方針が表示されます。`Recursive` の既定値は `No` で、`Tab` により `Yes` を選ぶとディレクトリ配下にも適用します。検索ワークスペースと native Windows では表示しません。 |
| `Compress as zip` | 対象が 1 件以上あるとき | 選択中の項目、または未選択時はフォーカス中の項目を zip 圧縮します。 |
| `Extract archive` | 単一の対応アーカイブファイルが選択中またはフォーカス中のとき | `.zip` / `.tar` / `.tar.gz` / `.tar.bz2` の展開を開始します。展開先入力は絶対パスと相対パスの両方に対応し、相対パスはアーカイブ親ディレクトリ基準で解決されます。初期値はアーカイブと同じ階層にある同名ディレクトリの絶対パスです。既存パスとの衝突がある場合は事前確認し、展開中は status bar に entry 件数ベースの進捗を表示します。 |
| `Open` | 単一ファイルが選択中またはフォーカス中のとき | フォーカス中のファイルを OS の既定アプリケーションで開きます。 |
| `Edit with terminal editor` | 単一ファイルが選択中またはフォーカス中のとき | フォーカス中のファイルを `editor.command` -> `$EDITOR` -> 組み込み既定値の順でターミナルエディタで開きます。 |
| `Edit with GUI editor` | 単一ファイルが選択中またはフォーカス中のとき | フォーカス中のファイルを設定済みの GUI エディタで開きます。 |
| `Copy path` | 対象が 1 件以上あるとき | 選択中のパス一覧、または未選択時はフォーカス中のパスをシステムクリップボードへコピーします。 |
| `Move to trash` | 対象が 1 件以上あるとき | 選択中の項目、またはフォーカス項目をゴミ箱へ移動します（既定では確認あり、設定で変更可能）。Windows では `send2trash` 経由で Recycle Bin を使います。 |
| `Open current directory with file manager` | 常に表示 | 現在ディレクトリを OS のファイルマネージャで開きます。 |
| `Open current directory with terminal` | 常に表示 | `config.toml` の設定を優先しつつ、zivo の current directory を起点に別ウィンドウの外部ターミナルを起動します。独立した作業や長時間の作業に使います。 |
| `Run shell command` | 常に表示 | 1 行入力から、現在ディレクトリで短い非対話コマンドをバックグラウンド実行します。ダイアログで cwd を確認でき、結果には exit code、stdout、stderr を保持します。結果画面で `r` を押すと再実行、`t` を押すと同じ cwd の外部ターミナルを開きます。対話コマンドには通常画面の `t` による foreground shell を使います。Windows では `powershell.exe`、次に `pwsh`、最後に `cmd.exe` を優先するため、構文は選ばれた Windows shell に従います。 |
| カスタムアクション | 登録済みの各 `[[actions.custom]]`（`when` と `extensions` 条件に合わない項目は無効） | `config.toml` に登録した再利用可能な名前付きアクションを表示します。実行前に展開後 command/cwd/mode を確認します。定型の非対話処理には `background`、対話処理には `terminal`、独立作業には `terminal_window` を使います。詳しくは [カスタムアクション](custom-actions.ja.md) を参照してください。 |
| `Bookmark this directory` / `Remove bookmark` | 常に表示 | 現在ディレクトリを `[bookmarks].paths` に追加または削除します。ラベルは現在状態を反映します。 |
| `Show hidden files` / `Hide hidden files` | 常に表示 | ブラウザ 3 ペインの隠しファイル表示を切り替えます。ラベルは現在状態を反映します。 |
| `Edit config` | 常に表示 | 起動時設定を編集するオーバーレイを開きます。優先ターミナルエディタ、GUI エディタプリセット、外部ターミナル起動モード、隠しファイル表示、ディレクトリサイズ表示、テキストプレビュー表示、画像プレビュー表示、画像プレビュー方式、PDF プレビュー表示、Office プレビュー表示、テーマ、ソート、貼り付け競合時の既定動作、削除確認の有無などを編集できます。オーバーレイ内には選択中の設定が何を変えるかの説明も表示されるため、README を見返さなくても挙動を判断できます。テーマ変更はその場で即時プレビューされます。 |
| `Create file` | 常に表示 | 現在ディレクトリで新規ファイル作成の入力を開始します。 |
| `Create directory` | 常に表示 | 現在ディレクトリで新規ディレクトリ作成の入力を開始します。 |
