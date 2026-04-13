# zivo Performance Notes

This note records the conditions for the main-flow integration test and the 1000-entry verification that were run in Issue #24 for MVP judgement.

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

## Current policy

- Automated benchmarks remain out of CI and release workflows
- The normal current pane uses viewport-aware projection, while summary and selected counts continue to reflect the full filtered entry set
- Performance checks stay manual and scenario-driven when behavior changes warrant them
