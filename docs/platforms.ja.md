# プラットフォーム別セットアップ

zivo の OS サポート状況と、各 OS で必要になる依存関係・セットアップ手順を説明します。

---

## サポート状況

| OS | サポート状況 | 備考 |
| --- | --- | --- |
| Ubuntu | サポート | 現時点で主要な動作確認対象です。 |
| Ubuntu (WSL) | サポート | WSL 上の Ubuntu を動作確認対象としています。 |
| macOS | サポート | ゴミ箱操作にはターミナルへのフルディスクアクセス権限が必要です。 |
| Windows | サポート | ドライブ移動、ファイル操作、クリップボード、シェルコマンド、外部ターミナル、undo などほとんどの機能を利用できます。`zivo-cd` は Windows では未対応です。zivo は Python アプリケーションとして Windows 上で動作します。スタンドアロンのネイティブ実行ファイルは提供されていません。 |

---

## 推奨ツール

zivo 本体の起動は `uv` だけで行えますが、一部の機能は `PATH` 上の外部コマンドに依存します。

| 機能 | 使用するツール |
| --- | --- |
| 画像プレビュー | `chafa`（`image_preview_mode = "kitty"` または `"auto"` 時、対応端末では Kitty graphics protocol を使用） |
| PDF プレビュー | 組み込み `pypdf`、任意の `pdftotext` / Poppler fallback |
| Office プレビュー | 組み込み OOXML テキスト抽出 |
| grep 検索 | `ripgrep` |

画像とgrepのツールは任意依存です。PDFテキスト抽出は組み込み`pypdf`を使い、インストール済みの`pdftotext`は完了した抽出失敗時だけ上限制付きfallbackとして使います。不足や非対応時もtracebackで終了せず、概要メタデータと利用可能な代替Actionを表示します。Officeプレビューに外部コマンドは必要ありません。

### CI のテスト範囲

CI の matrix では Ubuntu と macOS で `pytest` のフルスイートを実行します。ネイティブ Windows では、ファイル操作、クリップボード、アーカイブ展開・圧縮、ファイル検索・grep 検索、テキスト置換、設定、OOXML プレビュー抽出を対象にしたサポート対象の回帰テスト範囲を実行します（`tests/test_adapters_file_operations.py`、`tests/test_services_clipboard_operations.py`、`tests/test_services_file_mutations.py`、`tests/test_services_archive_extract.py`、`tests/test_services_zip_compress.py`、`tests/test_services_file_search.py`、`tests/test_services_grep_search.py`、`tests/test_services_text_replace.py`、`tests/test_services_config.py`、`tests/test_ooxml_preview.py`）。

Issue #1160 でフルスイートも検証しましたが、POSIX パス・改行の前提、chmod/chown のセマンティクス、OS 固有の UI タイミングにより、ネイティブ Windows で 24 件の失敗がありました。これらのテストを移植するまで、Windows の対象範囲は意図的に制限します。Windows でテストを skip する場合は、symlink 権限や権限セマンティクスなど、OS 固有の制約を理由としてテスト側に明記します。

### OS 別のインストール例

```bash
# Ubuntu / Debian (X11)
sudo apt install chafa poppler-utils ripgrep xclip

# Ubuntu / Debian (Wayland)
sudo apt install chafa poppler-utils ripgrep wl-clipboard

# Ubuntu (WSL)
sudo apt install chafa poppler-utils ripgrep wslu

# macOS
brew install chafa poppler ripgrep
```

### OS 別の詳細

#### Windows

Windows では、ドライブルート（`C:\` など）で `←` を押すとドライブ一覧に戻り、zivo を離れずにドライブを切り替えられます。

依存ツールは各公式サイトからインストールしてください。

- ドキュメントプレビュー: 組み込み OOXML テキスト抽出（外部コマンド不要）
- 画像プレビュー: [chafa](https://hpjansson.org/chafa/)（Kitty graphics protocol の利用には [Kitty](https://sw.kovidgoyal.net/kitty/)、[Ghostty](https://ghostty.org/)、[WezTerm](https://wezfurlong.org/wezterm/) などの対応端末が必要です）
- PDFプレビュー fallback (`pdftotext`): [poppler for Windows](https://github.com/oschwartz10612/poppler-windows)
- grep 検索: [ripgrep](https://github.com/BurntSushi/ripgrep)

#### macOS の権限設定

macOS では、使用しているターミナルアプリに **フルディスクアクセス** 権限を付与してください。

**システム設定 > プライバシーとセキュリティ > フルディスクアクセス** を開き、zivo を実行するターミナルアプリ（Terminal.app、iTerm2、Alacritty など）を有効にしてください。この権限がない場合、`~/.Trash` などの保護されたディレクトリにアクセスする操作が失敗します。

---

## WSL に関する注意点

- WSL では `wslu` のインストールを推奨します。`wslview` が利用可能になり、GUI 連携のブリッジ動作に使われます。
- zivo は WSL 上で `wslview`、`explorer.exe`、`clip.exe` のような Windows 側ブリッジを優先し、WSLg や Linux デスクトップ向けのフォールバックも維持します。

## シェルコマンドの構文

Run command（`!`）は macOS・Linux・WSL では現在の shell 環境を使い、未設定時は `/bin/bash` にフォールバックします。Windows では `powershell.exe`、`pwsh`、`cmd.exe` の順に優先するため、POSIX `sh` ではなく選ばれた shell の構文で入力してください。Run command は短い非対話作業向けです。プロンプトや TUI アプリには foreground shell（`t`）、独立した長時間作業には外部ターミナル（`T`）を使います。

---

## GUI 連携に関する注意

GUI 連携（既定アプリ起動、ファイルマネージャ起動、外部ターミナル起動など）は、主に Ubuntu と WSL 上の Ubuntu で確認しています。
