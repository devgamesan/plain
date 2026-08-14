# PDFプレビュー backend 判断記録

Issue #1184 の実装前に、既定のPDF preview backendを比較評価した記録です。

## 評価条件

- 実施日: 2026-08-14
- 環境: macOS arm64、Python 3.12
- 候補: `pypdf==6.16.0`
- 比較対象: Poppler `pdftotext` 26.08.0
- スクリプト: `scripts/benchmark_pdf_preview.py`
- corpus はスクリプトがPDF構文から一時ディレクトリへ生成する。第三者文書やfontはcommitしない。
- 暗号化fixtureは評価時だけpypdfの通常writerで生成する。zivoへ`crypto` extraは追加せず、password promptも行わない。

スクリプトは生成入力ごとのSHA-256を出力する。現在のrunでは次のfixtureを評価した。

| ケース | 目的 | SHA-256先頭 |
| --- | --- | --- |
| `simple_english` | 単純な英語単一段組 | `d7be769b70364313` |
| `unicode_japanese` | 日本語Unicode | `19e4d993a0818969` |
| `embedded_subset_font` | 合成した埋め込みsubset font descriptor | `220928059fa6d215` |
| `multi_page` | ページ境界と早期終了 | `9c863554b7b5f021` |
| `columns_and_table` | 段組・表に近い配置 | `2823ffb0d983fc7` |
| `rotated` | 変換された文字配置 | `fe06b1f1044af96a` |
| `empty_page` | 空ページ | `0da1530d5d4411bd` |
| `metadata_only` | metadataのみ | `5cb8d2e1778b39f5` |
| `scan_image_only` | テキスト層なし画像ページ | `950a9f5592e26f85` |
| `large_content_stream` | 1.4 MiB非圧縮content stream | `7e0d9d3c50409a85` |
| `many_pages` | 100ページとページ上限 | `35444a3a7bcecfe2` |
| `corrupt` | 切り詰めたPDF | `8b8cff24cf628e26` |
| `encrypted` | password保護PDF | `d7731b5a29906b35` |

corpusの生成内容はこのrepositoryで作成したもので、第三者fontは埋め込んでいない。subset font fixtureもオリジナルのPDF構文だけで生成し、外部font assetを同梱していない。日本語ケースの標準CMap名はPDF仕様の一部である。

## 観察結果

- 英語・日本語と埋め込みsubset fontケースはpypdfとpdftotextの双方で抽出できた。
- 複数ページ、段組、変換配置でもpypdfは内容確認に有用な文字列を得られた。空白や段組の順序はPDF抽出の性質上、完全一致を要求しない。
- 空ページ、metadataのみ、画像のみ、暗号化PDFは有用なtext previewとして扱わなかった。
- 100ページケースは64ページおよび64 KiB出力上限で停止した。
- 1.4 MiB content streamはworkerの1 MiB上限で`resource_limit`になった。直接in-processで試した場合は5秒上限を超えたため、runtimeで直接pypdfを呼ばない。
- worker起動を含むpypdfの通常ケースはこの環境で約0.4–0.7秒、pdftotextは約10–40msだった。これはCIの性能閾値ではなく、環境依存の参考値である。
- 大きなcontent streamはpdftotextなら抽出できるが、pypdfのresource limit後にfallbackすると安全上限を迂回するため、再試行しない。

## 判断

pypdfを主要なPDF text抽出backendとして採用する。ただし、次の制約をruntime契約とする。

1. 既存のbounded process runnerで使い捨てPython workerを起動する。timeout/cancel時はworkerを終了し、別backendを起動しない。
2. 入力、ページ、出力、content streamの上限を適用し、worker内のpypdf decoder上限もzivoのcontent stream budgetへ下げる。
3. pypdfがbudget内で完了し、`no_text_content`、`unsupported`、parser/corrupt errorになった場合だけpdftotextを最大1回使う。`cancelled`、`timeout`、`resource_limit`、`permission_denied`、`encrypted`、入力上限超過ではfallbackしない。
4. pypdfは通常のproduction依存として追加し、crypto/imageのoptional extraは追加しない。tested major version内でlockする。
5. backend選択は内部に隠し、既存のcache、無効化、reason、metadata fallback、`Open with default app`を維持する。

将来のpypdfで安全上限のhookが変わる場合やcorpus基準を満たさない場合は、制限を弱めずfallback順を再評価する。
