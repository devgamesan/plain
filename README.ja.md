# zivo

![CI](https://github.com/devgamesan/zivo/workflows/Python%20CI/badge.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.12+-blue.svg)
![Release](https://img.shields.io/github/v/release/devgamesan/zivo)
![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)

---
[English](README.md) | [日本語](README.ja.md)
---

zivo は、キーバインドをたくさん覚えなくても使える TUI ファイルマネージャです。

既定では、モードごとに整理した標準ショートカットを一定の順序でヘルプバーに表示し、低頻度の操作はコマンドパレットから検索して実行できます。ファイルの閲覧、プレビュー、検索、grep、置換、2 ディレクトリ間の転送をターミナル内で完結できます。

---

## zivo が向いている人

- TUI ファイルマネージャを使いたいが、キーバインド暗記が面倒な人
- ターミナル内でファイル閲覧・検索・移動・置換まで済ませたい人
- ranger / lf / nnn / yazi は便利だが少し玄人向けだと感じる人
- WSL やターミナル中心の環境で、GUI ファイラーに切り替えず作業したい人

---

## 主な特徴

- **覚えなくてOK**: 関連する標準ショートカットをヘルプバーに表示
- **状況適応コマンドパレット**: `:` を押すと、Navigate / File / Search / View / System / Custom actions のカテゴリを表示
- **3 ペインプレビュー**: ディレクトリ、テキスト、画像、PDF、Office ファイルを右ペインで確認
- **レスポンシブペイン**: 120 列以上は Parent / Current / Contents、80〜119 列は Current / Contents、80 列未満は `Tab` で current 一覧と Details を切り替え
- **明示的なペイン状態**: 空、フィルタ0件、読込中、設定無効、非対応、依存不足、権限不足、timeout、resource limitを区別し、安全な部分テキストには `Preview limited` を表示、プレビュー不能時は概要メタデータを表示
- **Transfer モード**: 2 つのディレクトリを並べてコピー・移動
- **検索と grep**: ファイル検索、grep 検索、表示中の結果から次の操作へ進む
- **置換 (プレビュー付き)**: Find / Grep / Search Workspace の結果を共通フローへ渡し、diff を確認してから実行
- **操作通知の次アクション**: Undo可能な成功には `Undo`、archive/zipの成功には移動先、許可された失敗には `Retry` または `Details` を表示し、Detailsには安全な復旧Actionを最大1件表示

---

3 ペインでディレクトリを移動しながら右ペインでファイルをプレビューできます。ファイル検索・grep機能により、目的のファイルに素早くジャンプできます。80 列未満の端末では `Tab` でカーソルや選択を保持したまま current 一覧と詳細ビューを切り替えられます。ヘルプバーは重要なショートカットを予測可能な順序で表示するため、迷わず操作できます。

パスバーにはクリック可能な breadcrumb segment と Back/Forward の可否を表示します。複数タブ時は active tab と、hover 時の close/new affordance を表示します。`Name`、`Size`、`Modified` の列ヘッダーをクリックしてsortでき、現在の方向と folders-first 状態も確認できます。狭い端末では現在地、active tab、Name列、sort状態を優先して表示します。

![基本的なディレクトリ閲覧とプレビュー](docs/resources/basic_operation.gif)

キーバインドを覚えていなくても `:` のコマンドパレットから必要な操作を検索して実行できます。コマンドはインクリメンタルサーチに対応しており、素早く目的のコマンドを実行できます。

![コマンドパレットの検索と実行](docs/resources/command_palette.gif)

Transfer モードでは、2つのディレクトリを左右に並べて、選択したファイルを反対側のペインへコピーまたは移動できます。`c` でコピー、`m` で移動でき、方向・件数はヘッダーに表示されます。
![Transfer モードでのコピーと移動](docs/resources/transfer_mode_operation.gif)

---

## インストール

### 前提条件

- Python 3.12 以上
- インストールと開発コマンドに使う [`uv`](https://docs.astral.sh/uv/)
- Textual UI を表示できるターミナル

zivo は Linux、macOS、Windows、Ubuntu on WSL で動作します。画像プレビューや
再帰 grep などの任意機能には外部コマンドが必要です。詳しくは
[Platforms](docs/platforms.ja.md) を参照してください。外部コマンドがなくても、基本的な
ファイル閲覧機能は利用できます。

### 最小構成

```bash
uv tool install zivo
```

### 追加インストールが必要な機能

基本的なファイル閲覧、PDF のテキストプレビュー、Office ファイルのテキストプレビューは、
追加コマンドなしで利用できます。次の機能を使う場合だけ、必要なコマンドを追加してください。

| 機能 | 追加インストール |
| --- | --- |
| 画像プレビュー | `chafa`（画像プレビューに必要。Kitty、Ghostty などの対応端末では高精細に表示） |
| PDF テキストプレビュー | 組み込み機能で読み取ります。読み取りに失敗した場合は、`pdftotext` がインストールされていれば補助的に使います |
| Office プレビュー | 追加インストール不要 |
| grep 検索 | `ripgrep` |

OS 別の詳しいセットアップは [Platforms](docs/platforms.ja.md) を参照してください。

---

## 起動

```bash
zivo
```

`zivo` 単体では親シェルのカレントディレクトリを変更できません。終了時に最後に見ていたディレクトリへ親シェルも追従させたい場合は、先に shell integration を読み込みます。

```bash
eval "$(zivo init bash)"  # bash 用
eval "$(zivo init zsh)"   # zsh 用
```

これにより `zivo-cd` というシェル関数が定義されます。終了後に親シェルを最後のディレクトリへ `cd` させたいときは、`zivo` ではなく `zivo-cd` で起動します。

```bash
zivo-cd
```

**注**: シェル統合 (`zivo-cd`) は現在 Windows ではサポートされていません。Windows では通常の `zivo` を使用してください。

---

## 基本操作

ヘルプバーは3つの論理行を一定の順序で表示します。Browsing はナビゲーション、ファイル操作、検索・作成の順です。Search Workspace は利用可能な項目だけを同じ相対順序で表示します。Transfer は対応するグループに Tab ペイン切替と反対ペインへのコピー・移動を追加します。狭い端末では行数を増やさず、各行の右端から低頻度の項目を省略します。

テキストプレビュー中は本文をマウスドラッグして範囲選択できます。選択後に `c` を押すか、右ペイン下部の `Copy selection` をクリックすると選択範囲をコピーします。`Esc` でプレビュー選択を解除できます。右ペイン下部には `Ctrl+J/K scroll preview` も表示します。置換プレビューでは `Shift+↑/↓ scroll preview` を表示し、通常プレビューの `Ctrl+↑/↓` も別名として使用できます。画像などテキスト以外のプレビューでは範囲選択を行いません。

マウスホイールはポインター直下のペインまたは結果一覧をスクロールします。ホイールでは表示位置だけが変わり、選択項目は変わりません。行をクリックすると選択できます。Preview のスクロールバーは表示し、ブラウザと検索・置換結果一覧のスクロールバーは表示領域を確保するため非表示にします。

すべての操作は `:` のコマンドパレットから検索して実行できます。

| キー | 操作 |
|---|---|
| `↑` / `↓` or `j` / `k` | 移動 |
| `Enter` | 開く / ディレクトリに入る |
| `←` / `h` | 親ディレクトリへ戻る |
| `Space` | 選択 |
| `:` | コマンドパレット |
| `/` | フィルタ |
| `f` | ファイル検索 |
| `g` | grep 検索 |
| `G` | 統合 Go 移動先検索 |
| `p` | Transfer モード切替 |
| `Tab`（80 列未満） | current 一覧と Details ビューを切り替え |
| `q` | 終了 |

詳しいキーバインドは [Keybindings](docs/keybindings.ja.md) を参照してください。

---

## コマンドパレット

`:` を押すと、利用可能な操作を検索して実行できます。クエリが空の場合は、Navigate / File / Search / View / System / Custom actions の固定カテゴリを表示します。全コマンドはマウスホイールでスクロールでき、`↑` / `↓` と `Ctrl+j` / `Ctrl+k` では選択行が常に表示範囲へ追従します。

検索では一般的な別名やキーワードも使えます。たとえば `duplicate` / `clone` で Duplicate、`trash` で Move to trash、`grep` や `search contents` で Grep search、`shell` でターミナル起動を検索できます。Duplicate は選択対象（未選択時はフォーカス対象）を元の親ディレクトリ内に自動命名で複製し、既存名を上書きしません。結果の順位は決定的に計算されます。現在の状態では実行できないコマンドも検索結果に残り、dim 表示と具体的な理由を示します。無効項目で Enter を押すと、同じ理由を warning で確認できます。カスタムアクションは登録済みの項目を常に表示し、設定済みの context 条件に合わない場合は無効理由を示します。名前でも検索できます。

詳しいコマンド一覧は [Commands](docs/commands.ja.md) を参照してください。

操作通知に表示する次アクションは最大1つです。優先順位は `Undo`、移動先の `Open`、安全な `Retry`、`Details` です。Detailsには安全な復旧Actionを最大1件だけ表示し、`[z] Undo completed items` または `[r] Retry` として実行できます。`Enter` と `Esc` は従来どおりDetailsを閉じます。5秒後に自動消去するのは最終成功通知だけで、処理中・warning/error・partial success は自動消去タイマーを持たず、新しい通知または関連する次アクションで状態が進むまで表示されます。StatusBar、Details、コマンドパレットの条件付き `Suggested` は同じ stable action ID と reducer 経路を使い、既存のグローバルキーボードの意味は変更しません。

時間のかかる Copy・Move・Compress・Extract・Replace は、StatusBarに操作名、進捗、現在対象を表示します。実行中も通常のブラウズ、ディレクトリ移動、ファイル検索、プレビュー、属性表示を継続できます。安全に停止できる操作だけ `Cancel` と `Esc` を表示し、キャンセル要求後は現在の対象を完了してから停止します。別のファイル変更、Undo、エディタ・シェル起動、変更を伴うカスタムアクションは、進行中の操作名を示して拒否します。部分完了時は成功・skip・failure・未処理件数を示し、対象パスとUndo可能範囲は `Details` で確認できます。

---

## サポート機能一覧

### ブラウズ
- **3 ペインブラウズ**: 左ペインでツリー、中央ペインでファイル一覧、右ペインでプレビュー
- **タブ**: 複数ディレクトリをタブで切り替え
- **ディレクトリ履歴**: 戻る / 進むで履歴移動
- **ブックマーク**: ディレクトリを保存し、`b` でブックマークに絞った Go 画面から移動
- **Go**: `G` でブックマーク、最近の履歴、開いているタブ、Home、直接パスを 1 画面で検索（`@bookmark`、`@history`、`@tab`、`@home` で source を絞り込み）。パス区切りの入力直後は、直接移動候補を残したまま直下の子ディレクトリ候補を読み込みます。
- **画面からの直接操作**: breadcrumb segment、通常ブラウズの Back/Forward、タブ、sort可能な列ヘッダーをクリックできます。Search Workspace は専用ラベルで表示します

### ファイル操作
- **コピー / カット / ペースト / Duplicate**: 同一ペイン内または Transfer モードで実行。Duplicate は元を残したまま同じ親ディレクトリへ安全に複製
- **リネーム**: インラインリネーム
- **権限・所有者変更**: POSIX 系ファイルシステムでは、コマンドパレットから選択対象の octal モードや所有者・グループを変更
- **削除**: ゴミ箱移動（`d`）または完全削除（`D`）、確認ダイアログ設定可能
- **Undo**: リネーム / ペースト / Duplicate / ゴミ箱移動を取り消し
- **複数選択**: Space で選択、Select all で一括選択

### アーカイブ
- **圧縮**: 選択項目を zip 圧縮
- **展開**: zip / tar / tar.gz / tar.bz2 を展開

### 検索・置換
- **ファイル検索**: 再帰的にファイル名を検索
- **grep 検索**: ripgrep による再帰検索。ディレクトリ・現在のファイル・選択ファイル・Search Workspace のスコープと、ファイル名 / 拡張子フィルタに対応
- **置換**: 現在のファイル、選択ファイル、ディレクトリ、Find / Grep / Search Workspace から明示的に渡した検索結果を対象に、diff 確認後に一括置換

### プレビュー

空ディレクトリとフィルタ0件では理由と実行可能な次の操作を表示します。現在ペインが隠し項目だけの場合は `[.] Show hidden files` を表示します。左ペインは読込中、権限不足、親なし、表示項目なしを区別し、再読込中もキャッシュ済み一覧を維持します。右ペインは読込時間・出力・resource limitを有限にし、読込中を明示します。安全な部分テキストには `Preview limited` を表示し、内容をプレビューできない場合は、種類、サイズ、更新日時、permission、owner/group、symlink target、archive entry countなどの概要へフォールバックします。任意の外部コマンドが不足してもアプリはクラッシュしません。
- テキスト、画像（`chafa`、対応端末では高精細表示）、PDF テキスト、Office テキストのプレビュー

### Transfer モード
- 2 ペインを左右に並べ、選択ファイルを反対側のペインへコピーまたは移動
- `Tab` で転送元/先ペインを切り替え、方向・パス・選択件数をヘッダーに表示
- `c` でコピー、`m` で、選択中（またはフォーカス中）の項目を反対側ペインへ移動

### コマンドパレット
- `:` で全操作をインクリメンタルサーチから実行。`G` で Go の移動先を横断検索でき、`~`、`[`、`]`、`b` の近道も維持

### カスタマイズ
- **設定オーバーレイ**: 起動時設定を対話的に編集・保存
- **カスタムアクション**: 外部ツールをコマンドパレットに追加
- **config.toml**: テーマ、ソート、プレビュー、エディタ、削除確認などの基本設定は Config Editor で、高度設定は設定ファイルで管理

### 外部連携
- **開く・編集する**: 選択ファイルを OS 既定アプリで開く、またはターミナル / GUI エディタで編集する
- **foreground shell**: zivo を一時停止して現在のターミナルで対話作業
- **ターミナル起動**: 独立作業用に現在ディレクトリを外部ターミナルウィンドウで開く
- **Run command**: 現在ディレクトリで短い非対話コマンドを実行し、exit code・出力・エラー詳細を保持
- **ファイルマネージャ**: 現在のディレクトリを OS のファイルマネージャで開く
- **クリップボード**: パスとテキストプレビューの選択範囲をシステムクリップボードにコピー

---

## 設定

zivo は初回起動時に `config.toml` を自動生成します。Config Editor では頻繁に変更する基本設定を扱い、`e` で高度設定を設定ファイルから編集できます。UI 保存時にも高度設定や未知の設定は保持され、外部エディタ終了後は設定ファイルを再読込します。
テーマ、プレビュー、ソート、エディタ連携、削除確認などを設定できます。
また、外部ツールを起動するカスタムアクションをコマンドパレットに追加できます。
ヘルプ文言自体は、現在の状態と標準キーマップから生成されます。

詳しくは [Configuration](docs/configuration.ja.md) を参照してください。
カスタムアクションの設定例と安全上の注意は [Custom Actions](docs/custom-actions.ja.md) を参照してください。

---

## 安全性について

zivo はファイル操作の事故を防ぐための安全機構を備えています。

- **ゴミ箱移動**: `d` / `Delete` で OS 標準のゴミ箱へ移動（確認ダイアログ表示可能）
- **完全削除**: `D` / `Shift+Delete` は常に確認後に実行
- **Undo**: `z` で直前のリネーム・貼り付け・ゴミ箱移動を取り消し
- **貼り付け競合解決**: 上書き / スキップ / リネームを選択可能
- **置換プレビュー**: diff preview で確認してから一括置換を実行
- **長時間操作の安全性**: Compressは一時アーカイブを作成して成功時だけ原子的に公開し、ExtractとReplaceも一時ファイル経由で置換します。キャンセルでworkerを強制停止せず、正式なdestinationに途中結果を残しません。
- **結果通知の次アクション**: Retry は、fresh preflight を行う競合なしの貼り付け失敗、適用済み変更がない Duplicate 失敗、archive/zip の準備失敗に限定します。partial result は失敗対象のパスと理由を `Details` に表示し、可能な場合だけ完了済みCopy/Move対象のUndoを提示します。
- **その他の詳細**: [Safety](docs/safety.ja.md) を参照

---

## 関連ドキュメント

- [Keybindings](docs/keybindings.ja.md) — 全キーバインド一覧
- [Commands](docs/commands.ja.md) — コマンドパレット全コマンド一覧
- [Custom Actions](docs/custom-actions.ja.md) — カスタムアクション設定ガイド
- [Configuration](docs/configuration.ja.md) — 設定ファイルの詳細
- [Platforms](docs/platforms.ja.md) — OS 別セットアップ
- [Safety](docs/safety.ja.md) — 安全仕様
- [Architecture](docs/architecture.ja.md) — 実装構造
- [Performance](docs/performance.ja.md) — 性能確認メモ
- [PDF Preview Decision](docs/pdf-preview-decision.ja.md) — PDF プレビュー方式の評価と上限
- [Release Checklist](docs/release-checklist.md) — リリースチェックリスト
- [Dependency and GitHub Actions Audit](docs/dependency-audit.ja.md) — CI依存関係監査とAction固定方針

---

## ライセンス

zivo は MIT ライセンスで提供されています。詳細は [LICENSE](LICENSE) を確認してください。

### サードパーティーライセンス

zivo はサードパーティーパッケージに依存しています。production runtime 依存と
ライセンス識別子の一覧は [NOTICE.txt](NOTICE.txt) に保持しています。依存パッケージは
zivo の wheel に同梱せず、それぞれ別の配布物としてインストールするため、ライセンス全文は
各依存パッケージの配布物に保持されます。

将来、依存コードを同梱した配布物を作る場合は、同梱する依存パッケージのライセンス全文も
その配布物に含めます。

production 依存関係を更新した後に NOTICE.txt を更新するには:

```bash
uv run --locked --no-sync python scripts/update_notice.py
```

---

> **ベータ版**: zivo は現在ベータ版です。機能追加、キーバインド見直しにより、キーバインドは変更の可能性があります。

## 開発者向け

開発環境を作る場合は次を実行します。

```bash
uv sync --python 3.12 --dev
```

ローカル checkout から直接アプリを起動する場合は、リポジトリ直下で次を使えます。

```bash
uv run zivo
```

テストと静的検査:

```bash
uv run ruff check .
uv run pytest
```

### TestPyPI からインストール

リリース前のバージョンをテストする場合は、TestPyPI からインストールできます:

```bash
uv tool install \
  --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ \
  --index-strategy unsafe-best-match \
  zivo
```
