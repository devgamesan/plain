# Peneo

[日本語版 README](README.ja.md)

Peneo is a Textual-based TUI file manager that aims to feel closer to a GUI explorer.
It is designed so you can reach the main actions without having to study a Vim-style key map first.

![Peneo screenshot](docs/resources/screen1.png)

_Current three-pane UI showing the parent, current, and child directories side by side._

## Features

- Three-pane layout for parent / current / child directories
- Keyboard-only navigation, selection, copy, cut, paste, delete, rename, and create flows
- Filter input, sort switching, and hidden-file visibility toggle
- Less frequent actions grouped into a command palette so everyday keys stay small in number
- Files open with the OS default app, `e` opens the current file in the editor inside the current terminal, and a terminal can also be launched in the current directory

## Current Capabilities

- Browse directories and move through the filesystem
- Multi-select files and directories
- copy / cut / paste
- Move items to trash
- Rename a single target
- Create files and directories
- Filter by file name
- Switch sorting by name / modified time / size
- Toggle directories-first ordering
- Copy paths to the system clipboard
- Launch a terminal in the current directory
- Toggle hidden-file visibility
- Open files with the OS default app
- Open files in the editor inside the current terminal

## Installation

With `uv` installed, clone the repository and install Peneo as a tool.

```bash
git clone https://github.com/devgamesan/peneo.git
cd peneo
uv tool install --from . peneo
```

To update, pull the latest changes and run the same install command again.

## Run

```bash
peneo
```

To launch directly from a local checkout during development, run this from the repository root:

```bash
uv run peneo
```

## Basic Operations

The main keys are listed below.

| State | Key | Behavior |
| --- | --- | --- |
| Normal | `↑` / `k` | Move the cursor |
| Normal | `↓` / `j` | Move the cursor |
| Normal | `←` / `h` / `Backspace` | Move to the parent directory |
| Normal | `→` / `l` | Enter the item if it is a directory |
| Normal | `Enter` | Enter a directory, or open a file with the default app |
| Normal | `e` | Open the focused file in the editor inside the current terminal |
| Normal | `F5` | Reload the current directory |
| Normal | `Space` | Toggle selection, then move to the next row |
| Normal | `y` | Copy the selected items, or the focused item if nothing is selected |
| Normal | `x` | Cut the selected items, or the focused item if nothing is selected |
| Normal | `p` | Paste into the current directory |
| Normal | `Delete` | Move the selected items, or the focused item, to trash |
| Normal | `F2` | Start rename input for a single target |
| Normal | `/` | Start filter input |
| Normal | `s` | Cycle the sort order |
| Normal | `d` | Toggle directories-first ordering |
| Normal | `Esc` | Clear the active filter, otherwise clear the selection |
| Normal | `:` | Open the command palette |
| Filter input | Text input | Update the filter string |
| Filter input | `Backspace` | Delete one character |
| Filter input | `Enter` / `↓` | Apply the filter and return to list navigation |
| Filter input | `Esc` | Clear the filter |
| Command palette | Text input / `↑` / `↓` / `k` / `j` / `Enter` / `Esc` | Filter, move, run, or cancel commands |
| Name input | Text input / `Backspace` / `Enter` / `Esc` | Edit, confirm, or cancel rename/create input |
| Confirmation dialog | `Enter` / `Esc` | Confirm or cancel delete |
| Confirmation dialog | `o` / `s` / `r` / `Esc` | Resolve a paste conflict with overwrite / skip / rename / cancel |

## Command Palette

Less frequent actions are grouped in the command palette opened with `:`.
The currently available commands are:

- `Create file`
- `Create directory`
- `Copy path`
- `Open terminal here`
- `Show hidden files` / `Hide hidden files`

Commands still under development may appear dimmed and cannot be executed yet.

## Platform Notes

- The project is currently verified only on Ubuntu.
- The code contains external-launch implementations for Linux / macOS / Windows, but not every platform path is fully validated.
- The application is still under active development, so behavior and keybindings may change.

## Related Documents

- Implementation structure: [docs/architecture.en.md](docs/architecture.en.md)
- MVP notes: [docs/spec_mvp.en.md](docs/spec_mvp.en.md)
- Performance notes: [docs/performance.en.md](docs/performance.en.md)

## Development

To prepare the development environment:

```bash
uv sync --python 3.12 --dev
```

Lint and test:

```bash
uv run ruff check .
uv run pytest
```
