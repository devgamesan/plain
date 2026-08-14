# コマンドパレット一覧

`:` で開くコマンドパレットで利用可能な全コマンドの一覧です。
属性表示、パスコピー、ブックマーク変更、外部アプリ起動、再読み込みなどの低頻度操作は、単一キーではなくこのパレットから実行します。移動先の検索は `Go` に統合しますが、`~`、`[`、`]`、`b` の近道は維持します。
Transferモードでは、アクティブな転送ペインで実行できるコマンドだけをコマンドパレットに表示します。反対側ペインへのコピー（`c`）・移動（`m`）も含まれます。`Tab` がペイン切替に使われるため、キーボードのブラウザタブ操作はパレット中心ですが、表示中のタブバーはマウスで切替・close・新規タブを実行できます。
タブバーは 2 タブ以上開いている場合にだけ表示されます。

> 想定読者: 基本操作を理解したうえで、検索可能なコマンド一覧を確認したい利用者。

通常ブラウズでは、パスバーにクリック可能な breadcrumb segment と Back/Forward を表示します。タブバーではタブ切替、hover 時の close、新規タブの affordance を利用できます。中央ペインの `Name`、`Size`、`Modified` header は sort に使えます。これらのマウス操作は、対応するキー操作・パレット操作と同じ Action を使用します。Transfer modeでも既存のキーボード・パレットの意味を維持し、パスバーに履歴ボタンは追加しません。

クエリが空の場合は、実効対象（`Selection`、`Target`、`Current folder`）と、実行可能な `Suggested` 操作を最大5件表示し、その下に残りのコマンドをカテゴリ別に表示します。Suggested に表示したコマンドは一覧で重複させません。明示選択の外側にあるフォーカスは `not included` と明示します。Pasteは現在のフォルダへの操作として `Paste 2 items here` のように表示します。文字を入力すると全コマンドを絞り込め、無効なコマンドも理由付きで表示されます。カテゴリ順とコマンド順位は決定的で、利用履歴やテレメトリは使用しません。

Directory History と Go の最近の履歴は、最後に訪問したディレクトリから新しい順に表示します。各タブと Transfer の各ペインは、最新の重複しないディレクトリパスを100件までメモリに保持し、古い項目を自動的に破棄します。

待機する terminal editor、foreground terminal、shell command、`terminal` / `background` のカスタムアクションが完了したとき、実行 cwd または編集対象ファイルの親が表示中の実ディレクトリと一致すれば、そのディレクトリを1回だけ再読込します。既存のカーソル、選択、filter、sort は再読込後も適用されます。GUI editor、新しい terminal window、既定アプリ起動、configだけを更新するoverlay完了、Search Workspace、archive 専用表示はこの完了時再読込の対象外です。

最新の操作に次アクションがある場合、空の `commands` パレットではそのActionを `Suggested` の先頭に置き、残りを文脈操作で補充して、実行可能な項目を合計最大5件表示します。通知の優先順位は `Undo`、`Open destination`、安全な `Retry`、`Details` です。Detailsには安全な復旧Actionを最大1件だけ表示し、`[z] Undo completed items` または `[r] Retry` として実行できます。`Enter` / `Esc` はDetailsを閉じます。StatusBar、Details、通知由来の `Suggested` は同じ stable action ID と reducer 経路を共有し、既存のグローバルキーボード経路は現在の意味を維持します。新しいグローバルキーは追加しません。表示開始から5秒で自動消去するのは最終成功通知だけで、処理中・warning/error・partial success は自動消去しません。

`Retry` は、成功・skip・overwrite がなく、元の `PasteRequest` の conflict resolution が未指定である貼り付け失敗、成功・適用済み変更がない Duplicate 失敗、archive/zip 準備失敗に限定します。Retry は毎回 fresh preparation/preflight を行い、競合や対象変更があれば既存の競合確認・再確認経路へ戻ります。`Details` は失敗件数、対象パス、理由を表示し、有効なUndoエントリがある場合だけ完了済みCopy/Move対象のUndoを提示します。`Enter` または `Esc` で閉じます。

コマンド一覧全体はマウスホイールでスクロールできます。キーボードのカーソル移動（`↑` / `↓` または `Ctrl+j` / `Ctrl+k`）では、選択行が自動的に表示範囲へ追従します。

検索ではコマンドの keywords と一般的な別名にも一致します。ラベル完全一致、ラベル前方一致、単語前方一致、部分一致、決定的な fuzzy 一致の順で順位付けします。無効なコマンドも検索対象に残り、具体的な理由を表示します。無効項目で Enter を押すと実行せず同じ理由を warning で通知します。カスタムアクションは設定済みの context 条件を維持し、名前で検索できます。

| コマンド | 表示条件 | 動作 / 補足 |
| --- | --- | --- |
| `New tab` | 常に表示 | 現在ディレクトリを初期値にした新しいブラウズタブを開きます。 |
| `Next tab` | 2 タブ以上開いているとき | 次のブラウズタブへ切り替えます。 |
| `Previous tab` | 2 タブ以上開いているとき | 前のブラウズタブへ切り替えます。 |
| `Close current tab` | 2 タブ以上開いているとき | アクティブなブラウズタブを閉じます。最後の 1 タブは閉じられません。 |
| `Find files` | 常に表示 | `Keyword`、`Target`、`Include extensions`、`Exclude extensions` の入力欄を持つ再帰ファイル名検索を開きます。拡張子は `py, js` のようなカンマ/空白区切り（先頭の `.` は任意、大文字小文字を区別しない）で入力できます。キーワードと拡張子フィルターは AND で評価し、拡張子を指定した場合はキーワードを空にできます。`Target=files` は一致するファイル、`Target=all` は拡張子指定中は一致するファイルだけを返し、ディレクトリ検索では拡張子フィルターを解除する必要があります。 |
| `Grep search` | 常に表示 | 共通の再帰コンテンツ検索を開きます（`ripgrep` / `rg` が `PATH` 上に必要）。従来の `search contents` も検索用 alias として利用できます。current directory / selected files/directories / Search Workspace（Search Workspace を開いているときだけ選択可能）の scope を選択でき、keyword / filename / include extension / exclude extension の各フィルタを共通で利用できます。選択したディレクトリは再帰的に検索します。 |
| `Go` | 常に表示 | `G` で Home、ブックマーク、最近の履歴、開いているタブ、直接パスを 1 画面で検索します。入力先頭に `@bookmark`、`@history` / `@recent`、`@tab`、`@home` を付けると source を絞れます。`b` は同じ画面をブックマーク限定で開きます。`/`（Windowsでは `/` または `\\`）の入力直後は、入力中のディレクトリを Enter 用の先頭候補に残したまま、直下の子ディレクトリを非同期で表示します。`j` / `k` は通常の入力文字で、選択移動には矢印キーまたは `Ctrl+j` / `Ctrl+k` を使います。 |
| `Go back` | ディレクトリ履歴に戻り先があるとき | 履歴を一つ戻ります。 |
| `Go forward` | ディレクトリ履歴に進み先があるとき | 履歴を一つ進みます。 |
| `Go to home directory` | 常に表示 | ホームディレクトリへ移動します。 |
| `Enter folder` | 明示選択なしでディレクトリにフォーカスがあるとき | 既存のディレクトリ移動Actionを使って、フォーカス中のディレクトリへ移動します。 |
| `Reload directory` | 常に表示 | 現在ディレクトリを再読み込みします。 |
| `Toggle transfer mode` / `Close transfer mode` | 常に表示 | 通常の 3 ペインブラウザと 2 ペイン転送レイアウトを切り替えます。 |
| `Show preview or contents` / `Back to file list` | 80 列未満の通常ブラウズでフォーカス対象があるとき | 狭い端末で表示するビューを current のファイル一覧と詳細ペイン（プレビュー／検索結果）の間で切り替えます。ラベルは現在のビューに応じて変わり、直接キーは `Tab` です。Search Workspace の `Tab` は入力欄移動を維持します。 |
| `Undo last file operation` | Undo 履歴があるとき | 直前の Undo 対象リネーム、貼り付け、複製、ゴミ箱移動を取り消します。 |
| `Select all` | 現在ディレクトリに表示中の項目が 1 件以上あるとき | 現在ディレクトリで表示中の項目をすべて選択します。 |
| `Save results` | grep 検索結果を表示中 | 現在の grep 結果を現在のディレクトリの `grep_results.txt` へ保存します。設定済みの grep プレビュー context 行を含み、既存ファイルは変更しません。 |
| `Replace text` | 常に表示 | Scope を選べる単一の置換パレットを開きます。初期 Scope は選択状態に応じて Selected files、Current file、Current directory になります。Find/Grep の結果画面では `Replace results`（`Ctrl+r`でも実行）、Search Workspace では `Replace selected results` を選べます。表示中のファイルが固定 `Search results` Scope として渡され、右ペインで diff をプレビューしてから確認・適用します。 |
| `Show attributes` | 単一対象が選択中またはフォーカス中のとき | 読み取り専用の属性ダイアログを開きます。 |
| `Rename` / `Rename N items` | 対象が 1 件以上あるとき（Search Workspace を除く） | 1 件なら従来の単一対象リネーム、2 件以上なら Old Name / New Name / Status を確認できる一括リネームオーバーレイを開きます。Base name を入力すると、元の拡張子を保った連番の New Name を自動生成します。`Rename items` は全行を再検証してから実行し、衝突・不正名・対象消失などがあれば適用しません。通常ブラウズと Transfer の両方で利用できます。 |
| `Change permissions` | Linux / macOS / WSL の実ファイルシステム上の 1 件以上の対象が選択中またはフォーカス中のとき | 選択中の全対象、または未選択時はフォーカス対象の permission 変更入力を開始します。`755` や `644` のような 3 桁 octal mode を入力します。ダイアログには対象数・種別と、symlink をスキップしてリンク先を辿らない方針が表示されます。`Recursive` の既定値は `No` で、`Tab` により `Yes` を選ぶとディレクトリ配下にも適用します。検索ワークスペースと native Windows では表示しません。Windows は `chmod` 経由で POSIX permission bit を表現できないため対象外です。 |
| `Change owner` | Linux / macOS / WSL の実ファイルシステム上の 1 件以上の対象が選択中またはフォーカス中のとき | 選択中の全対象、または未選択時はフォーカス対象の owner/group 変更入力を開始します。`owner`、`owner:group`、`:group` を入力できます。ダイアログには対象数・種別と、symlink をスキップしてリンク先を辿らない方針が表示されます。`Recursive` の既定値は `No` で、`Tab` により `Yes` を選ぶとディレクトリ配下にも適用します。検索ワークスペースと native Windows では表示しません。 |
| `Compress as zip` | 対象が 1 件以上あるとき | 選択中の項目、または未選択時はフォーカス中の項目を zip 圧縮します。 |
| `Extract archive` | 単一の対応アーカイブファイルが選択中またはフォーカス中のとき | `.zip` / `.tar` / `.tar.gz` / `.tar.bz2` の展開を開始します。展開先入力は絶対パスと相対パスの両方に対応し、相対パスはアーカイブ親ディレクトリ基準で解決されます。初期値はアーカイブと同じ階層にある同名ディレクトリの絶対パスです。既存パスとの衝突がある場合は事前確認し、展開中は status bar に entry 件数ベースの進捗を表示します。 |
| `Open` | 単一ファイルが選択中またはフォーカス中のとき | フォーカス中のファイルを OS の既定アプリケーションで開きます。 |
| `Edit with terminal editor` | 単一ファイルが選択中またはフォーカス中のとき | フォーカス中のファイルを `editor.command` -> `$EDITOR` -> 組み込み既定値の順でターミナルエディタで開きます。 |
| `Edit with GUI editor` | 単一ファイルが選択中またはフォーカス中のとき | フォーカス中のファイルを設定済みの GUI エディタで開きます。 |
| `Copy path` | 対象が 1 件以上あるとき | 選択中のパス一覧、または未選択時はフォーカス中のパスをシステムクリップボードへコピーします。 |
| `Duplicate` | 通常の実ファイルシステムで対象が 1 件以上あるとき | 選択中の各対象、または未選択時はフォーカス対象を現在の親ディレクトリ内へ複製します。既存項目を上書きせず、拡張子を維持した `copy`、`copy 2`、`copy 3` の順で空き名を選びます。ファイル、ディレクトリ、symlink に対応し、進捗・対象別失敗・成功結果を通知します。成功した複製先は 1 回の Undo 単位になります。 |
| `Move to trash` | 対象が 1 件以上あるとき | 選択中の項目、またはフォーカス項目をゴミ箱へ移動します（既定では確認あり、設定で変更可能）。Windows では `send2trash` 経由で Recycle Bin を使います。 |
| `Permanently delete` | 対象が 1 件以上あるとき | 選択中の項目、またはフォーカス項目を完全に削除します。常に確認が必要で、複数対象またはディレクトリを含む場合は既存の `Enter` → `D` 二段階確認を行い、Undoできません。 |
| `Open current directory with file manager` | 常に表示 | 現在ディレクトリを OS のファイルマネージャで開きます。 |
| `Open current directory with terminal` | 常に表示 | `config.toml` の設定を優先しつつ、zivo の current directory を起点に別ウィンドウの外部ターミナルを起動します。独立した作業や長時間の作業に使います。 |
| `Run shell command` | 常に表示 | 1 行入力から、現在ディレクトリで短い非対話コマンドをバックグラウンド実行します。ダイアログで cwd を確認でき、結果には exit code、stdout、stderr を保持します。結果画面で `r` を押すと再実行、`t` を押すと同じ cwd の外部ターミナルを開きます。対話コマンドには通常画面の `t` による foreground shell を使います。Windows では `powershell.exe`、次に `pwsh`、最後に `cmd.exe` を優先するため、構文は選ばれた Windows shell に従います。 |
| カスタムアクション | 登録済みの各 `[[actions.custom]]`（`when` と `extensions` 条件に合わない項目は無効） | `config.toml` に登録した再利用可能な名前付きアクションを表示します。実行前に展開後 command/cwd/mode を確認します。定型の非対話処理には `background`、対話処理には `terminal`、独立作業には `terminal_window` を使います。詳しくは [カスタムアクション](custom-actions.ja.md) を参照してください。 |
| `Bookmark this directory` / `Remove bookmark` | 常に表示 | 現在ディレクトリを `[bookmarks].paths` に追加または削除します。ラベルは現在状態を反映します。 |
| `Show hidden files` / `Hide hidden files` | 常に表示 | ブラウザ 3 ペインの隠しファイル表示を切り替えます。ラベルは現在状態を反映します。 |
| `Clear filter` | 名前フィルタが有効でクエリがあるとき | 既存の filter reducer 経路を使って、現在ペインのフィルタを解除します。 |
| `Edit config` | 常に表示 | 起動時設定を編集するオーバーレイを開きます。優先ターミナルエディタ、GUI エディタプリセット、OS 別の外部ターミナル起動テンプレート、隠しファイル表示、ディレクトリサイズ表示、テキストプレビュー表示、画像プレビュー表示、画像プレビュー方式、PDF プレビュー表示、Office プレビュー表示、テーマ、ソート、貼り付け競合時の既定動作、削除確認の有無などを編集できます。オーバーレイ内には選択中の設定が何を変えるかの説明も表示されるため、README を見返さなくても挙動を判断できます。テーマ変更はその場で即時プレビューされます。 |

空・フォールバック状態のペインには、実行可能なローカルActionだけを表示します。空の現在ディレクトリでは `Create`、フィルタ0件では `Clear filter`、隠し項目だけの場合は `[.] Show hidden files`、非対応・依存不足・変換エラー・timeout・resource limit・テキストなしのプレビューでは `Open with default app`、権限不足など診断を優先する状態では `Show attributes`、設定で無効な場合は `Edit config` を表示します。カーソルまたはプレビュー対象が変わった古いActionは起動せず、warningを表示します。クリック時も既存コマンドと同じreducer経路を使用し、共有external launcherによるディレクトリのファイルマネージャ起動は維持します。左ペインは読込中、権限不足、親なし、表示項目なしを区別し、再読込中もキャッシュ済み一覧を維持します。
| `Create` | 常に表示 | ファイル／ディレクトリを一つのフローで作成します。Type を明示的に選び、必要なら不足したサブディレクトリを含む相対パスを入力して、親ディレクトリと最終対象のプレビューを確認して実行します。`n` は File、`N` は Directory を初期選択します。 |
