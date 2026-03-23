# Repository Guidelines

## Project Structure & Module Organization

Core application code lives under `src/plain/`. Keep UI concerns in `src/plain/ui/`, state and reducers in `src/plain/state/`, side-effect orchestration in `src/plain/services/`, external integrations in `src/plain/adapters/`, and shared data models in `src/plain/models/`. Tests live in `tests/`. Product and MVP notes belong in `docs/`. CI is defined in `.github/workflows/python-ci.yml`.

Current input handling is centralized in `src/plain/state/input.py`. Keep key interpretation in the dispatcher and reducer-facing actions rather than embedding per-widget branching in `src/plain/ui/`.

## Build, Test, and Development Commands

- `uv sync --python 3.12 --dev`: create or refresh the local environment with dev dependencies.
- `uv run plain`: start the Textual app through the console script.
- `uv run python -m plain`: alternate module-based entrypoint.
- `uv run ruff check .`: run lint checks.
- `uv run pytest`: execute the test suite.

Run commands from the repository root so paths and config resolution stay consistent.

## Coding Style & Naming Conventions

Target Python 3.12 and follow PEP 8 with 4-space indentation. Use `snake_case` for modules, functions, and variables; `PascalCase` for classes; and short imperative names for actions or commands. Keep UI code presentation-focused and move filesystem or OS-specific logic into `adapters/` and `services/`. Use `ruff` for import sorting and lint enforcement before opening a PR.

## Testing Guidelines

Use `pytest` for all tests and `pytest-asyncio` for async or Textual headless cases. Name test files `test_*.py` and test functions `test_*`. Add or update tests with every behavior change. New UI bootstrap or state transitions should have at least one smoke-level test proving the app can start or the reducer path works.

The current app supports three-pane rendering backed by a dummy `AppState`, plus keyboard handling for core browsing/filter flows. Covered interactions include cursor movement with `Up` / `Down`, selection toggle with `Space`, selection clear with `Esc`, entering filter mode with `/`, and filter editing/confirm/cancel while in `FILTER` mode. Real filesystem navigation and file operations such as open, copy, delete, rename, create, and paste are still not implemented; keep AGENTS/README in sync when that changes.

## Commit & Pull Request Guidelines

Recent history uses short imperative commit subjects such as `Add MVP specification document`. Follow that style and keep commits focused. Create feature branches per issue, for example `feat/issue-7-textual-bootstrap`. PR titles should include the related issue ID, and PR descriptions should summarize scope, test results, and follow-up work. Link the issue, and include terminal output or screenshots when a UI change is easier to review visually.

## Configuration & Workflow Notes

Use `gh` for GitHub operations. Keep `.venv/`, cache directories, and editor-specific files out of commits. Update `README.md` when setup steps, commands, or repository layout change.
