# 依存関係と GitHub Actions の監査

CI で実施する依存関係監査と GitHub Actions のサプライチェーン対策を説明します。

> 想定読者: 依存関係更新、CI変更、監査結果を確認するメンテナー。

## CI での確認内容

`dependency-audit` ジョブは、Python CI workflow の対象となるすべての PR と push について、Ubuntu 上で一度だけ実行されます。

1. `uv lock --check` で、`uv.lock` とプロジェクト設定の整合性を確認します。
2. `uv export --frozen --no-dev --no-emit-project` で production 依存だけを書き出します。
3. `pip-audit` で既知の脆弱性を検査し、検出時はCIを失敗させます。

既存の Linux、macOS、Windows のマトリクスでは lint とテストを継続します。依存関係監査は繰り返しません。

## ローカルで監査する

リポジトリ直下で実行します。

```bash
uv sync --python 3.12 --dev
uv lock --check
uv export --frozen \
  --no-dev \
  --no-emit-project \
  --format requirements.txt \
  --output-file .venv/zivo-production-requirements.txt
uv run --locked --no-sync pip-audit \
  --no-deps \
  --disable-pip \
  --requirement .venv/zivo-production-requirements.txt
```

生成される requirements ファイルはコミット対象外の `.venv/` 配下に置かれます。

production runtime 依存のライセンス情報は `NOTICE.txt` に保持します。
wheel は `pypdf`、`send2trash`、`textual` を `Requires-Dist` で宣言するだけで、
依存コードを同梱しません。そのため、依存ライセンス全文を zivo wheel に重複収録せず、
各依存パッケージの配布物に保持されるライセンス情報を利用します。NOTICE は固定した
production 依存から次のコマンドで再生成します。

```bash
uv run --locked --no-sync python scripts/update_notice.py
```

将来、依存コードを同梱した配布物を作る場合は、同梱するすべての依存パッケージの
ライセンス全文をその配布物に含めます。

## 脆弱性が見つかった場合

`pip-audit` が脆弱性を報告した場合は、可能であれば影響を受ける production 依存を修正版へ更新し、`uv.lock` を再生成して監査を再実行します。CIログには対象パッケージ、アドバイザリ、利用可能な修正版が表示されます。

ignore オプションの追加や、export 対象から依存を除外することで監査を回避してはいけません。

## 一時的な例外申請

すぐに更新できない場合は、関連する Issue または PR で一時的な例外を申請します。次の情報を記載してください。

- パッケージ名、アドバイザリID、影響を受けるバージョン範囲
- 修正版を採用できない理由
- 代替対策または緩和策
- 担当者と明確な期限または見直し日

例外にはメンテナーの承認が必要です。例外は一時的なものであり、依存関係またはリリース workflow の変更時に見直します。

## GitHub Actions の固定方針

`.github/workflows/` 内の外部 `uses:` 参照は、すべて40文字のコミットSHAを使用します。レビュー用にバージョンやブランチ名をインラインコメントで残せますが、実行される参照には使用しません。

SHA固定できないActionがある場合は、技術的な理由と、mutable参照を許可する正確なworkflow範囲をPRに記載する必要があります。現在、この例外はありません。
