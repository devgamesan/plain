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
| 画像プレビュー | `chafa` |
| PDF プレビュー | `pdftotext` / `poppler` |
| Office プレビュー | `pandoc` |
| grep 検索 | `ripgrep` |

### OS 別のインストール例

```bash
# Ubuntu / Debian (X11)
sudo apt install chafa pandoc poppler-utils ripgrep xclip

# Ubuntu / Debian (Wayland)
sudo apt install chafa pandoc poppler-utils ripgrep wl-clipboard

# Ubuntu (WSL)
sudo apt install chafa pandoc poppler-utils ripgrep wslu

# macOS
brew install chafa pandoc poppler ripgrep
```

**注**: 一部のディストリビューションでは、パッケージマネージャー経由で pandoc 3.8.3 以上が提供されない場合があります。インストールされたバージョンが 3.8.3 より古い場合は、[公式 pandoc ウェブサイト](https://pandoc.org/installing.html) から最新版を手動でインストールしてください。

### OS 別の詳細

#### Windows

Windows では、ドライブルート（`C:\` など）で `←` を押すとドライブ一覧に戻り、zivo を離れずにドライブを切り替えられます。

依存ツールは各公式サイトからインストールしてください。

- ドキュメントプレビュー: [pandoc](https://pandoc.org/)
- 画像プレビュー: [chafa](https://hpjansson.org/chafa/)
- PDFプレビュー (`pdftotext`): [poppler for Windows](https://github.com/oschwartz10612/poppler-windows)
- grep 検索: [ripgrep](https://github.com/BurntSushi/ripgrep)

#### macOS の権限設定

macOS では、使用しているターミナルアプリに **フルディスクアクセス** 権限を付与してください。

**システム設定 > プライバシーとセキュリティ > フルディスクアクセス** を開き、zivo を実行するターミナルアプリ（Terminal.app、iTerm2、Alacritty など）を有効にしてください。この権限がない場合、`~/.Trash` などの保護されたディレクトリにアクセスする操作が失敗します。

---

## WSL に関する注意点

- WSL では `wslu` のインストールを推奨します。`wslview` が利用可能になり、GUI 連携のブリッジ動作に使われます。
- zivo は WSL 上で `wslview`、`explorer.exe`、`clip.exe` のような Windows 側ブリッジを優先し、WSLg や Linux デスクトップ向けのフォールバックも維持します。

---

## GUI 連携に関する注意

GUI 連携（既定アプリ起動、ファイルマネージャ起動、外部ターミナル起動など）は、主に Ubuntu と WSL 上の Ubuntu で確認しています。
