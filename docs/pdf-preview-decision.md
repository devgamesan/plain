# PDF Preview Backend Decision

This record captures the Issue #1184 evaluation before changing the default PDF
preview backend.

> Audience: maintainers evaluating PDF preview behavior, dependencies, and safety limits.

## Evaluation setup

- Date: 2026-08-14
- Host: macOS arm64, Python 3.12
- Candidate: `pypdf==6.16.0`
- External comparator: Poppler `pdftotext` 26.08.0
- Script: `scripts/benchmark_pdf_preview.py`
- The corpus is generated in a temporary directory from PDF syntax authored in
  the script. No third-party document or font is committed.
- The encrypted case is generated with pypdf's default RC4-compatible writer
  path only for evaluation. zivo does not add the `crypto` extra or prompt for
  passwords.

The script prints SHA-256 values for every generated input so an evaluation run
can be audited. The current run produced these corpus entries:

| Case | Purpose | SHA-256 prefix |
| --- | --- | --- |
| `simple_english` | ordinary single-column text | `d7be769b70364313` |
| `unicode_japanese` | Japanese Unicode text using a standard PDF CMap | `19e4d993a0818969` |
| `embedded_subset_font` | embedded synthetic subset-font descriptor | `220928059fa6d215` |
| `multi_page` | page boundary and early output | `9c863554b7b5f021` |
| `columns_and_table` | positioned columns and table-like text | `2823ffb0d983fc7` |
| `rotated` | transformed text placement | `fe06b1f1044af96a` |
| `empty_page` | empty page | `0da1530d5d4411bd` |
| `metadata_only` | metadata with no text | `5cb8d2e1778b39f5` |
| `scan_image_only` | image-only page with no text layer | `950a9f5592e26f85` |
| `large_content_stream` | 1.4 MiB uncompressed content stream | `7e0d9d3c50409a85` |
| `many_pages` | 100 pages and page limit | `35444a3a7bcecfe2` |
| `corrupt` | truncated PDF | `8b8cff24cf628e26` |
| `encrypted` | password-protected PDF | `d7731b5a29906b35` |

All generated corpus content is original work in this repository. No embedded
third-party font is redistributed. The standard CMap name in the Japanese case
is part of the PDF format and is not a bundled font asset.

## Observations

- English and Japanese text, including the embedded synthetic subset-font case,
  were extracted correctly by pypdf and pdftotext. The subset-font fixture is
  original PDF syntax; it does not redistribute an external font.
- pypdf preserved useful text for the multi-page, positioned-column, and
  transformed-text cases. Exact whitespace and column order remain heuristic,
  as expected for PDF extraction.
- Empty, metadata-only, image-only, and encrypted files were not treated as
  useful text previews.
- The 100-page case stopped at 64 pages and the 64 KiB output budget.
- The 1.4 MiB content stream was rejected as `resource_limit` after the worker
  applied a 1 MiB stream cap. An earlier direct in-process probe exceeded the
  five-second budget, so direct pypdf extraction is not acceptable for the
  runtime path.
- With a disposable worker, ordinary pypdf cases completed in roughly 0.4–0.7
  seconds on this host, including interpreter startup. `pdftotext` completed in
  roughly 10–40 ms. These are local observations, not CI performance gates.
- The existing Poppler fallback recovered text from the large content stream,
  but the safety policy intentionally does not retry after a pypdf resource
  limit. The user receives the safety-limit state and can use the existing
  external-app action.

## Decision

Adopt pypdf as the primary PDF text extraction backend, subject to the runtime
constraints below:

1. Run extraction in a disposable Python worker with the existing bounded
   process runner. Timeout or cancellation terminates the worker and does not
   invoke another backend.
2. Apply input, page, output, and content-stream limits before/through the
   pypdf extraction path. The worker caps pypdf's decoder limits to the zivo
   content-stream budget.
3. Use `pdftotext` at most once only when pypdf completed within budget with
   `no_text_content`, `unsupported`, or a parser/corrupt error. Do not fallback
   after `cancelled`, `timeout`, `resource_limit`, `permission_denied`,
   `encrypted`, or input-size rejection.
4. Add `pypdf` as a normal production dependency without optional crypto/image
   extras. Keep the final lock range within the tested major version.
5. Keep backend selection internal. Existing cache keys, disabled behavior,
   reason states, metadata fallback, and `Open with default app` remain intact.

If a later pypdf release changes these safety hooks or fails the corpus gate,
the fallback order must be re-evaluated instead of silently weakening limits.
