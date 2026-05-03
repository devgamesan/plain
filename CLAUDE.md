# Repository Guidelines

## Project Structure & Module Organization

Core application code lives under `src/zivo/`. Keep UI concerns in `src/zivo/ui/`, state and reducers in `src/zivo/state/`, side-effect orchestration in `src/zivo/services/`, external integrations in `src/zivo/adapters/`, and shared data models in `src/zivo/models/`. Tests live in `tests/`. Product and MVP notes belong in `docs/`. CI is defined in `.github/workflows/python-ci.yml`.

Current input handling is centralized in `src/zivo/state/input.py`. Keep key interpretation in the dispatcher and reducer-facing actions rather than embedding per-widget branching in `src/zivo/ui/`.

## Build, Test, and Development Commands

- `uv sync --python 3.12 --dev`: create or refresh the local environment with dev dependencies.
- `uv run zivo`: start the Textual app through the console script.
- `uv run python -m zivo`: alternate module-based entrypoint.
- `uv run ruff check .`: run lint checks.
- `uv run pytest`: execute the test suite.

Run commands from the repository root so paths and config resolution stay consistent.

## Coding Style & Naming Conventions

Target Python 3.12 and follow PEP 8 with 4-space indentation. Use `snake_case` for modules, functions, and variables; `PascalCase` for classes; and short imperative names for actions or commands. Keep UI code presentation-focused and move filesystem or OS-specific logic into `adapters/` and `services/`. Use `ruff` for import sorting and lint enforcement before opening a PR.

## Testing Guidelines

Use `pytest` for all tests and `pytest-asyncio` for async or Textual headless cases. Name test files `test_*.py` and test functions `test_*`. Add or update tests with every behavior change. New UI bootstrap or state transitions should have at least one smoke-level test proving the app can start or the reducer path works.

The current app renders a live three-pane filesystem browser and routes keyboard input through the centralized dispatcher/reducer flow. Covered interactions include directory navigation, reload, filtering, sort changes, directories-first toggle, selection, copy/cut/paste, delete-to-trash with configurable confirmation, single-target rename, create file/directory flows, recursive file search from the command palette, read-only attribute inspection, startup-config editing and saving, opening files with the OS default app, opening files in a terminal editor with `e`, copying paths to the system clipboard, opening a terminal in the current directory with optional `config.toml` overrides, and toggling hidden-file visibility from the command palette. History navigation is fully implemented: `[`/`]` (or `Go back`/`Go forward`) traverses the back/forward stacks (pushed on each directory change, forward cleared on new navigation), and `H` (or `History search`) shows the full directory history list (`visited_all`).

## Commit & Pull Request Guidelines

Recent history uses short imperative commit subjects such as `Add MVP specification document`. Follow that style and keep commits focused. Create feature branches per issue from the latest `develop` branch, for example `feat/issue-7-textual-bootstrap`. Treat `develop` as the next release candidate and keep it in a state that is ready for functional verification. Merge feature work by opening PRs from the feature branch into `develop`. Except for hotfixes, do not merge work branches directly into `main`; release by merging `develop` into `main`. PR titles should include the related issue ID, and PR descriptions should summarize scope, test results, and follow-up work. Link the issue, and include terminal output or screenshots when a UI change is easier to review visually.

## Configuration & Workflow Notes

Use `gh` for GitHub operations. Sync the latest `develop` branch before creating a feature branch, and keep the hotfix exception explicit when a direct `main` update is required. Keep `.venv/`, cache directories, and editor-specific files out of commits. Update `README.md` when setup steps, commands, repository layout, or developer workflow change.
