# zivo

![CI](https://github.com/devgamesan/zivo/workflows/Python%20CI/badge.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.12+-blue.svg)
![Release](https://img.shields.io/github/v/release/devgamesan/zivo)
![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)

---
[English](README.md) | [日本語](README.ja.md)
---

zivo is a TUI file manager designed to be usable without memorizing dozens of shortcuts.

By default, it keeps a stable, mode-specific set of standard shortcuts visible in the help bar, and lets you run lower-frequency actions from the command palette. You can browse, preview, search, grep, replace, and transfer files without leaving the terminal.

---

## Who zivo is for

- People who want a terminal file manager without memorizing many shortcuts
- People who want to browse, preview, search, grep, and replace files from the terminal
- People who find ranger, lf, nnn, or yazi powerful but somewhat expert-oriented
- People who work mainly in terminals or WSL and want to avoid switching to a GUI file manager

---

## Highlights

- **No memorization required**: relevant standard shortcuts are shown in the help bar
- **Context-aware command palette**: press `:` to browse fixed Navigate, File, Search, View, System, and Custom actions sections
- **Three-pane preview**: preview directories, text, images, PDF, and Office files
- **Responsive panes**: 120+ columns show Parent / Current / Contents, 80–119 show Current / Contents, and narrower terminals use `Tab` to switch between the current file list and Details
- **Explicit pane states**: distinguish empty, filtered, loading, disabled, unsupported, dependency-missing, and permission-denied states; unavailable previews fall back to compact file metadata
- **Transfer mode**: copy and move files between two directories side by side
- **Search and grep**: find files, grep recursively, and continue from visible results
- **Replace with preview**: pass Find/Grep/Workspace results into one flow, review diffs, then apply a batch replacement
- **Actionable operation notifications**: successful undoable operations offer `Undo`, archive/zip results offer destination navigation, and allowlisted failures offer `Retry` or `Details`; Details can expose one safe recovery action

---

Browse directories across three panes while previewing files on the right. Use file search and grep to quickly jump to any file. On terminals below 80 columns, press `Tab` to switch between the current file list and the details view without losing the cursor or selection. The help bar keeps the important shortcuts in a predictable order, so you never feel lost.

The path bar exposes clickable breadcrumb segments and Back/Forward availability. When multiple tabs are open, the tab strip shows the active tab and mouse-only close/new affordances. Click `Name`, `Size`, or `Modified` headers to sort; the active direction and folders-first state remain visible. Narrow terminals keep the current path, active tab, Name column, and sort state visible while eliding lower-priority details.

![](docs/resources/basic_operation.gif)

Press `:` to search and run any action from the command palette. The palette supports incremental search, letting you find and execute commands quickly without memorizing keybindings.

![](docs/resources/command_palette.gif)

Transfer mode puts two directories side by side for easy copy and move operations.
Press `c` to copy or `m` to move selected items to the opposite pane; the header shows the direction and counts.
![](docs/resources/transfer_mode_operation.gif)

---

## Installation

### Minimal installation

```bash
uv tool install zivo
```

### Recommended tools

Some features use external commands.

| Feature | Tool |
| --- | --- |
| Image preview | `chafa` |
| PDF preview | `pdftotext` / `poppler` |
| Office preview | `pandoc` |
| Grep search | `ripgrep` |

See [Platforms](docs/platforms.md) for OS-specific setup instructions.

---

## Run

```bash
zivo
```

`zivo` itself cannot change the current directory of the parent shell. If you want your shell to follow the last directory you visited after quitting zivo, add shell integration first:

```bash
eval "$(zivo init bash)"  # for bash
eval "$(zivo init zsh)"   # for zsh
```

This defines a shell function named `zivo-cd`. Start zivo with `zivo-cd` when you want the parent shell to `cd` into the last directory on exit:

```bash
zivo-cd
```

**Note**: Shell integration (`zivo-cd`) is currently not supported on Windows. Use plain `zivo` on Windows.

---

## Basic controls

The help bar keeps three logical rows with a stable order. Browsing shows navigation, file operations, and search/create actions. Search Workspace keeps only the available subset in the same relative order. Transfer adds Tab pane switching and copy/move-to-opposite-pane actions to the corresponding groups. On narrow terminals, each row elides lower-frequency items from the right without adding extra rows.

When a preview is active, the footer of the right pane shows `Ctrl+J/K scroll preview`. The replace-preview screen uses `Shift+↑/↓ scroll preview`; `Ctrl+↑/↓` is an alias for the normal preview controls.

The mouse wheel scrolls the pane or result list under the pointer. Wheel scrolling changes the visible position without changing the selected item; click a row to select it. Preview scrollbars remain visible, while browser and search/replace result lists keep them hidden to preserve display width.

You can also press `:` to open the command palette and search for available actions.

| Key | Action |
|---|---|
| `↑` / `↓` or `j` / `k` | Move cursor |
| `Enter` | Open file / enter directory |
| `←` / `h` | Go to parent directory |
| `Space` | Toggle selection |
| `:` | Open command palette |
| `/` | Filter entries |
| `f` | Find files |
| `g` | Grep search |
| `G` | Open unified Go destination search |
| `p` | Toggle Transfer mode |
| `Tab` (below 80 columns) | Toggle current file list / Details view |
| `q` | Quit |

See [Keybindings](docs/keybindings.md) for the full list.

---

## Command palette

Press `:` to search and run available actions. With an empty query, the palette shows fixed Navigate, File, Search, View, System, and Custom actions sections. The full list is scrollable with the mouse wheel; `↑` / `↓` and `Ctrl+j` / `Ctrl+k` keep the selected row visible.

Search accepts common aliases and keywords such as `duplicate` or `clone` for Duplicate, `trash` for Move to trash, `grep` or `search contents` for Grep search, and `shell` for opening a terminal. Duplicate copies the selected targets (or the focused target) beside the originals, automatically choosing a non-conflicting `copy`, `copy 2`, and so on name. Results are ranked deterministically. Commands that do not apply remain searchable but are dimmed with a concrete reason; pressing Enter on one shows the same reason as a warning. Registered custom actions are always listed, while actions that do not satisfy their configured context conditions are disabled with a reason; they are also searchable by name.

See [Commands](docs/commands.md) for the full command list.

Operation notifications show at most one next action. The priority is `Undo`, destination `Open`, safe `Retry`, then `Details`. A Details overlay may expose at most one additional safe recovery action: `[z] Undo completed items` or `[r] Retry`; `Enter` and `Esc` still close it. Only final success notifications auto-dismiss after five seconds; processing, warning/error, and partial-success notifications stay visible without an auto-dismiss timer until a newer notification or its associated action advances the flow. The status bar, Details overlay, and the command palette's conditional `Suggested` entry use the same action ID and reducer path, while existing global keyboard meanings remain unchanged.

Long-running Copy, Move, Compress, Extract, and Replace operations show their operation name, progress, and current target in the status bar. Normal browsing, directory navigation, file search, preview, and attribute inspection remain available while they run. Safe operations expose `Cancel` and `Esc`; cancellation finishes the current item before stopping. Other file mutations, Undo, editor or shell launches, and mutation-capable custom actions are rejected with the active operation name. Partial results report succeeded, skipped, failed, and not-processed counts, with paths and Undo scope available from `Details`.

---

## Features

### Browsing
- **Three-pane layout**: directory tree on the left, file list in the center, preview on the right
- **Tabs**: open multiple directories and switch between them
- **Directory history**: go back / forward through visited directories
- **Bookmarks**: save directories and open them from the bookmark-filtered Go view with `b`
- **Go**: press `G` to search bookmarks, recent history, open tabs, Home, or a direct path in one view; use `@bookmark`, `@history`, `@tab`, or `@home` prefixes to filter the source. After a path separator, direct navigation remains available while child-directory candidates load.
- **Direct UI controls**: click breadcrumb segments, Back/Forward (normal browsing), tabs, and sortable column headers; Search Workspace uses a dedicated non-breadcrumb label

### File operations
- **Copy / Cut / Paste / Duplicate**: within a pane (normal mode only); Duplicate keeps the original and creates a safe same-directory copy
- **Rename**: inline single-item rename, or a reviewable `Rename N items` editor for two or more selected items (base-name numbering, extension preservation, validation, progress, and same-directory staging)
- **Permissions and ownership**: change selected targets' octal mode or owner/group from the command palette on POSIX-style filesystems
- **Move to trash**: `d` / `Delete` moves items to the OS trash; the operation can be undone when supported
- **Permanently delete**: `D` / `Shift+Delete` permanently deletes items; confirmation shows target count, total size, representative names, and an irreversible-operation warning
- **Undo**: revert rename, paste, duplicate, or trash operations
- **Multi-selection**: select files with Space, or Select all

### Archives
- **Compress**: zip selected items
- **Extract**: extract zip / tar / tar.gz / tar.bz2

### Search and replace
- **Find files**: recursive filename search
- **Grep search**: recursive content search via ripgrep with directory, current-file, selected-files, or Search Workspace scopes and common filename / extension filters
- **Replace**: one scope-aware flow for current file, selected files, directories, and explicitly passed Search results from Find, Grep, or Search Workspace

### Preview

Empty directories and zero-result filters show their reason and an available next action. When all current entries are hidden, the current pane offers `[.] Show hidden files`. The parent pane distinguishes loading, permission denied, no parent directory, and no visible items; cached parent entries remain visible during refresh. The right pane shows loading state explicitly and, when content preview is unavailable, falls back to a compact summary such as type, size, modified time, permissions, owner/group, symlink target, or archive entry count. Missing optional commands are reported without crashing the application.
- Text, images (chafa; optional Kitty graphics protocol on compatible terminals), PDF (pdftotext), Office (pandoc)

### Transfer mode
- Side-by-side two-pane layout for copying or moving files between directories
- `Tab` switches the source/destination pane; the header shows direction, paths, and selection count
- `c` copies and `m` moves the selected (or focused) items to the opposite pane

### Command palette
- Press `:` to search and execute any action via incremental search. No need to memorize keybindings
- Lower-frequency attribute, path-copy, bookmark-edit, external-launch, and reload actions live in the palette; `G` opens the unified Go destination search while `~`, `[`, `]`, and `b` remain quick paths

### Customization
- **Settings overlay**: interactively edit and save startup configuration
- **Custom actions**: add external tools to the command palette
- **config.toml**: use the Config Editor for common themes, sorting, previews, editors, and delete confirmation; edit advanced settings in the raw file

### External integration
- **Open and edit**: open a selected file with its OS default app, or edit it with a terminal or GUI editor
- **Foreground shell**: suspend zivo for interactive work in the current terminal
- **Terminal**: open the current directory with an external terminal window for independent work
- **Run command**: run a short non-interactive command in the current directory, with retained exit/output/error details
- **File manager**: open the current directory with the OS file manager
- **Clipboard**: copy paths to the system clipboard

---

## Configuration

zivo automatically creates `config.toml` on first launch.
The Config Editor covers commonly changed themes, previews, sorting, editor integration, and delete confirmation. Press `e` there to edit advanced settings in `config.toml`; saving from the UI preserves advanced and unknown settings, and zivo reloads the file when the external editor exits.
You can also add custom command palette actions for external tools.
Help text itself is generated from the current state and standard keybindings.

See [Configuration](docs/configuration.md) for details.
See [Custom Actions](docs/custom-actions.md) for custom action examples and safety notes.

---

## Safety

zivo includes safety mechanisms to prevent data loss during file operations.

- **Move to trash**: `d` / `Delete` moves items to the OS trash (confirmation dialog configurable)
- **Permanently delete**: `D` / `Shift+Delete` always asks for confirmation; multiple targets or directories require `Enter` followed by an explicit uppercase `D`
- **Undo**: `z` reverses the last rename, bulk rename, paste, or trash operation
- **Paste conflict resolution**: choose overwrite, skip, or rename on name collision
- **Actionable results**: retry is limited to fresh-preflight paste failures without conflicts, duplicate failures with no applied changes, and archive/zip preparation failures. Partial results expose failed paths and reasons in `Details`; when valid, Details offers Undo for completed Copy/Move items only.
- **Replace preview**: review diffs before applying batch replacements
- **Safe long-running operations**: Compress writes to a temporary archive and atomically publishes it; Extract and Replace write temporary files before replacement. Cancellation never force-stops a worker or leaves a partial temporary output as the final destination.
- **More details**: see [Safety](docs/safety.md)

---

## Related Documents

- [Keybindings](docs/keybindings.md) — full keybinding reference
- [Commands](docs/commands.md) — complete command palette reference
- [Configuration](docs/configuration.md) — configuration file details
- [Custom Actions](docs/custom-actions.md) — command palette custom action guide
- [Platforms](docs/platforms.md) — OS-specific setup
- [Safety](docs/safety.md) — safety specifications
- [Architecture](docs/architecture.en.md) — implementation structure
- [Performance](docs/performance.en.md) — performance notes
- [Release Checklist](docs/release-checklist.md) — release checklist
- [Dependency and GitHub Actions Audit](docs/dependency-audit.md) — CI dependency and action supply-chain audit policy

---

## License

zivo is licensed under the MIT License. See [LICENSE](LICENSE) for details.

### Third-Party Licenses

zivo depends on third-party packages. For a complete list of dependencies and their licenses, see [NOTICE.txt](NOTICE.txt).

To update NOTICE.txt after dependency changes:

```bash
uv run pip-licenses --format=plain --from=mixed --with-urls --output-file NOTICE.txt
```

---

> **Beta**: zivo is currently in beta. Keybindings may change as features are added and keybindings are reviewed.

## Development

To prepare the development environment:

```bash
uv sync --python 3.12 --dev
```

To launch the app directly from a local checkout, run this from the repository root:

```bash
uv run zivo
```

Lint and test:

```bash
uv run ruff check .
uv run pytest
```

### Install from TestPyPI

For testing pre-release versions, install from TestPyPI:

```bash
uv tool install \
  --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ \
  --index-strategy unsafe-best-match \
  zivo
```
