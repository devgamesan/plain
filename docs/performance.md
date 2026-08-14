# zivo Performance Notes

This note records the conditions for the main-flow integration test and the 1000-entry verification that were run in Issue #24 for MVP judgement.

> Audience: contributors comparing performance regressions against the recorded smoke tests.

## Date

- 2026-03-27
- 2026-03-28

## Environment

- OS: Linux 6.17.0-19-generic
- Python: 3.12.3
- Command: `uv run pytest`

## Automated Checks

- `tests/test_app.py::test_app_main_flow_round_trip_on_live_filesystem`
  - Uses the real filesystem to verify launch, navigation, selection, copy, paste, filter, and sort switching in one scenario
- `tests/test_app.py::test_app_large_directory_smoke_with_1000_entries`
  - Creates 200 directories and 800 files for a total of 1000 entries
  - Verifies the initial render, a 1000-entry list, 150 cursor moves, and continued child-pane updates

## Observations

- `uv run pytest tests/test_app.py -k large_directory_smoke_with_1000_entries --durations=1 -q`
  - `20.30s call     tests/test_app.py::test_app_large_directory_smoke_with_1000_entries`
  - The time above includes test data creation, Textual headless startup, and 150 key sends
- `uv run pytest tests/test_app.py -k 'main_flow_round_trip_on_live_filesystem or large_directory_smoke_with_1000_entries'`
  - `2 passed, 38 deselected in 21.92s`
- Even at the 1000-entry scale, the headless integration smoke test completed successfully, and the symptom where list rendering or child-pane updates stopped midway did not reproduce
- As part of Issue #104 on 2026-03-28, we added regression coverage to reuse current-pane visible entries inside `select_shell_data()` and to ensure cursor-only movement does not call `DataTable.clear()` / `add_row()` in `MainPane`
- `uv run python -m pytest tests/test_state_selectors.py -q`
  - `38 passed in 0.16s`
- `uv run python -m pytest tests/test_app.py -k 'refresh or large_directory_smoke_with_1000_entries' -q`
  - `4 passed, 41 deselected in 13.49s`
- Those checks preserved the 1000-entry smoke case while verifying that a single cursor move no longer rebuilds current-pane rows

## Known Constraints

- The current measurement is a regression-oriented smoke check, not a CI benchmark
- The recorded time is for the full test execution, not an isolated rendering-only measurement
- Perceived speed and scroll rendering cost in a real terminal can vary with the terminal emulator and font settings

## Rerun Commands

```bash
uv run pytest tests/test_app.py -k large_directory_smoke_with_1000_entries --durations=1 -q
uv run pytest tests/test_app.py -k main_flow_round_trip_on_live_filesystem -q
uv run python -m pytest tests/test_state_selectors.py -q
uv run python -m pytest tests/test_app.py -k 'refresh or large_directory_smoke_with_1000_entries' -q
```

## Issue #304 Viewport-Aware Projection Spike

### Date

- 2026-04-05

### Added for the spike

- `scripts/benchmark_current_pane_projection.py`
  - manual benchmark script comparing current-pane `cursor move`, `page scroll`, `selection toggle`, and `directory size` reflection under `full` vs `viewport`
- `create_app(..., current_pane_projection_mode="viewport")`
  - comparison-only spike that keeps `DataTable` and limits current-pane rendering to a terminal-height-derived window
- Formal adoption in Issue #326
  - on 2026-04-05, viewport-aware projection became the default runtime path and gained regression coverage for `pageup` / `pagedown` / `home` / `end`, filter and sort changes, hidden-file toggles, reloads, and resize handling

### Measurement setup

- Python: `uv run python`
- terminal height: 24
- viewport window: 16 rows
- the benchmark focuses on the `select_shell_data()` projection/update-hint path
- this is a local manual benchmark for Issue #304, not a CI benchmark

### Re-run commands

```bash
uv run python scripts/benchmark_current_pane_projection.py --entries 10000 --iterations 200
uv run python scripts/benchmark_current_pane_projection.py --entries 50000 --iterations 100
```

### Observations

#### 10,000 entries

| mode | operation | rendered rows | mean |
| --- | --- | ---: | ---: |
| full | cursor move | 10000 | 5.26 ms |
| full | page scroll | 10000 | 4.77 ms |
| full | selection toggle | 10000 | 5.27 ms |
| full | directory size reflect | 10000 | 8.55 ms |
| viewport | cursor move | 16 | 2.48 ms |
| viewport | page scroll | 16 | 2.48 ms |
| viewport | selection toggle | 16 | 2.42 ms |
| viewport | directory size reflect | 16 | 2.45 ms |

#### 50,000 entries

| mode | operation | rendered rows | mean |
| --- | --- | ---: | ---: |
| full | cursor move | 50000 | 26.59 ms |
| full | page scroll | 50000 | 24.39 ms |
| full | selection toggle | 50000 | 26.50 ms |
| full | directory size reflect | 50000 | 42.46 ms |
| viewport | cursor move | 16 | 12.25 ms |
| viewport | page scroll | 16 | 12.10 ms |
| viewport | selection toggle | 16 | 12.11 ms |
| viewport | directory size reflect | 16 | 12.27 ms |

### Decision notes

- Keeping `DataTable` and windowing only the current-pane projection already lowers the cost consistently
- The improvement is about 2x at 10,000 entries and up to about 3.5x for `directory size` reflection at 50,000 entries
- Even after windowing, the 50,000-entry case still spends about 12 ms per call, so fixed costs outside projection remain
- That means we cannot conclude that virtualization is unnecessary; at minimum, excluding offscreen rows from current-pane projection is worth pursuing
- Issue #326 promoted that direction from a comparison spike to the normal implementation path
- `current_pane_projection_mode` remains as an internal benchmark/test switch, while normal startup now uses viewport projection by default

## Issue #281 Go path completion

Direct-path completion in the unified Go palette uses a short debounce, a worker, and a short-lived parent-directory listing cache. Results are capped at 500 entries and the UI tells users to type more characters when the cap is reached.

Run the manual comparison with:

```bash
uv run python scripts/benchmark_go_completion.py --dirs 5000 --iterations 10
```

The benchmark separates cold listing from cached prefix filtering. It is intentionally not part of CI.

On 2026-08-12 (macOS, 5,000 directories, 10 iterations), the local run measured 14.26 ms mean / 18.41 ms p95 for cold listing and 0.31 ms mean / 0.37 ms p95 for cached `directory_000` filtering.

## Current policy

- Automated benchmarks remain out of CI and release workflows
- The normal current pane uses viewport-aware projection, while summary and selected counts continue to reflect the full filtered entry set
- Performance checks stay manual and scenario-driven when behavior changes warrant them

## Preview resource budget

Preview is a supporting feature and uses one internal budget across backends. Timeout,
converter stdout/stderr retention, converter input size, and built-in OOXML ZIP
entry/uncompressed-size/compression-ratio checks are finite. These limits are exposed as
advanced `[preview]` settings with safe defaults tuned so normal previews remain responsive.

Images use a separate budget from text converters: 2 MiB for symbols output, 32 MiB for
the Kitty graphics protocol, and a 15-second image converter timeout. This keeps ordinary
image review usable while still bounding retained output and execution time.

Measure normal and large PDF/Office/image files in cold and warm runs, time to first useful
content, peak memory, and rapid cursor movement. Safe text output is shown as `Preview limited`;
partial image or Kitty graphics output is not rendered and falls back to metadata. Cancelled
and stale results are not stored as successful preview cache entries.

Automated tests use short timeouts, fake converters, excessive stdout/stderr, ZIP-bomb-like
metadata, and paths containing spaces. Large performance benchmarks remain manual and are not
added to CI.

### Issue #1183 built-in OOXML benchmark

The manual `scripts/benchmark_ooxml_preview.py` benchmark uses synthetic DOCX/XLSX/PPTX
packages and measures cold/warm wall time, synchronous time-to-first-useful-content, and
Python peak allocations for the built-in loader:

| fixture | items | cold / warm |
| --- | ---: | ---: |
| DOCX | 1,000 | 16.29 / 14.81 ms |
| XLSX | 1,000 | 19.66 / 17.07 ms |
| PPTX | 1,000 | 110.58 / 107.31 ms |

The required text-order and representative-cell/slide/paragraph fixtures pass in
`tests/test_ooxml_preview.py`. Office previews use this in-process backend and do not require
an external document converter.
