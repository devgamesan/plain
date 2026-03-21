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

現時点ではプレースホルダの Textual アプリが起動します。3 ペイン本体や状態管理の詳細は後続 Issue で実装します。

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
- OS 依存処理やファイル操作は adapter/service 側へ隔離する
- まずはプレースホルダ起動、lint、test が安定して通る土台を優先する

