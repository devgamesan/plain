# Peneo

[日本語版 README](README.ja.md)

Peneo is a Textual-based TUI file manager designed for desktop environments where terminal work still needs to connect smoothly with GUI applications.
It aims to feel closer to a GUI explorer than to a keyboard-heavy power-user tool, and keeps common actions visible in the on-screen help so you can start using it without memorizing a Vim-style key map.

![Peneo screenshot](docs/resources/screen1.png)

_Current three-pane UI showing the parent, current, and child directories side by side._

## Features

- Three-pane layout for parent / current / child directories so surrounding filesystem context stays visible
- Optional embedded split terminal below the browser panes, opened and closed with a single shortcut and focused immediately
- Common actions stay visible in the on-screen help, while less frequent actions live in the command palette
- Keyboard-only navigation, multi-selection, copy, cut, paste, delete-to-trash, rename, and create flows
- Filter input, recursive file search from the command palette, attribute inspection, config editing, sort switching, and hidden-file visibility toggle
- Files open with the OS default app, directories can be opened in the OS file manager, `e` opens the current file in the editor inside the current terminal, and a terminal can also be launched in the current directory
- Optional shell integration via `peneo-cd` can return your shell to the last directory after quitting
- Safer file operations with trash deletion and overwrite / skip / rename conflict resolution during paste

## Current Capabilities

- Browse directories and move through the filesystem
- Multi-select files and directories
- copy / cut / paste
- Move items to trash
- Rename a single target
- Create files and directories
- Filter by file name
- Search files recursively from the command palette
- Inspect file and directory attributes from the command palette
- Edit startup config values from the command palette and save them back to `config.toml`
- Switch sorting by name / modified time / size
- Toggle directories-first ordering
- Copy paths to the system clipboard
- Open the current directory in the OS file manager
- Launch a terminal in the current directory
- Open an embedded split terminal rooted at the current directory
- Toggle hidden-file visibility
- Open files with the OS default app
- Open files in the editor inside the current terminal
- Persist display, behavior, and terminal-launch preferences in `config.toml`
- Optionally return the shell to the last visited directory after quitting

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

If you want the last directory from Peneo to become your shell's current directory when you quit, you can optionally enable shell integration:

```bash
eval "$(peneo init bash)"
# or
eval "$(peneo init zsh)"
```

After that, launch the optional wrapper instead of `peneo`:

```bash
peneo-cd
```

This setup is optional. Normal usage with `peneo` or `uv run peneo` still works without any shell configuration.

## Configuration File

On startup, Peneo reads `config.toml` from the platform-specific user config directory.
If the file does not exist yet, Peneo creates it automatically with default values.

- Linux: `${XDG_CONFIG_HOME:-~/.config}/peneo/config.toml`
- macOS: `~/Library/Application Support/peneo/config.toml`
- Windows config path is reserved for future compatibility, but native Windows runtime is still unsupported

Available sections:

- `terminal`: optional OS-specific terminal launch command templates, using `{path}` as the working directory placeholder
- `display`: default hidden-file visibility and sort settings
- `behavior`: delete-confirmation and paste-conflict defaults

Example:

```toml
[terminal]
linux = ["konsole --working-directory {path}", "gnome-terminal --working-directory={path}"]
macos = ["open -a Terminal {path}"]
windows = ["wt -d {path}"]

[display]
show_hidden_files = false
default_sort_field = "name"
default_sort_descending = false
directories_first = true

[behavior]
confirm_delete = true
paste_conflict_action = "prompt"
```

Invalid config values do not stop startup. Peneo falls back to built-in defaults and shows a warning after the initial directory load.

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
| Normal | `Delete` | Move the selected items, or the focused item, to trash (confirmation is enabled by default and can be configured) |
| Normal | `F2` | Start rename input for a single target |
| Normal | `/` | Start filter input |
| Normal | `s` | Cycle the sort order |
| Normal | `d` | Toggle directories-first ordering |
| Normal | `q` | Quit the app |
| Normal | `Esc` | Clear the active filter, otherwise clear the selection |
| Normal | `:` | Open the command palette |
| Normal | `Ctrl+T` | Open or close the embedded split terminal |
| Normal (with split terminal open) | Text input and browser shortcuts | Disabled while the split terminal owns input |
| Filter input | Text input | Update the filter string |
| Filter input | `Backspace` | Delete one character |
| Filter input | `Enter` / `↓` | Apply the filter and return to list navigation |
| Filter input | `Esc` | Clear the filter |
| Command palette | Text input / `↑` / `↓` / `k` / `j` / `Enter` / `Esc` | Filter commands, or search and jump to files |
| Split terminal focus | Text input / arrows / `Enter` / `Backspace` / `Esc` / `Tab` | Send input directly to the embedded shell |
| Split terminal focus | `Ctrl+T` | Close the embedded split terminal |
| Name input | Text input / `Backspace` / `Enter` / `Esc` | Edit, confirm, or cancel rename/create input |
| Confirmation dialog | `Enter` / `Esc` | Confirm or cancel delete |
| Confirmation dialog | `o` / `s` / `r` / `Esc` | Resolve a paste conflict with overwrite / skip / rename / cancel |

## Command Palette

Less frequent actions are grouped in the command palette opened with `:`.
The currently available commands are:

- `Find file`
- `Show attributes` (single target only)
- `Copy path`
- `Open in file manager`
- `Open terminal here`
- `Open split terminal` / `Close split terminal`
- `Show hidden files` / `Hide hidden files`
- `Edit config`
- `Create file`
- `Create directory`

`Find file` searches recursively under the current directory using a case-insensitive partial match on the filename, then jumps to the selected result by opening its parent directory and focusing that file. Hidden paths are excluded unless hidden-file visibility is enabled. Filesystem scans start after a short pause while you type, and if you keep narrowing a completed result set the palette filters it immediately without another full-tree walk. When there are many hits, the palette shows a moving window around the current cursor so you can inspect all matches with the arrow keys without clipping the list.

`Show attributes` opens a read-only dialog for the current cursor target or a single selected entry and shows `Name`, `Type`, `Path`, `Size`, `Modified`, `Hidden`, and `Permissions`.

`Edit config` opens an overlay for startup defaults such as hidden-file visibility, sort settings, delete confirmation, and paste-conflict handling. Use `↑` / `↓` to move between settings, `←` / `→` / `Enter` to change the selected value, `s` to save back to `config.toml`, and `e` to open the raw config file in your editor for terminal command templates or manual edits.

`Open split terminal` starts an embedded shell rooted at the current directory. The split terminal does not automatically follow later directory changes in the browser pane; open a new split session if you need a shell in another directory.

Commands still under development may appear dimmed and cannot be executed yet.

## Platform Notes

- The project is currently verified only on Ubuntu.
- GUI integration paths such as default-app launch, file-manager launch, and terminal launch are currently validated primarily in that environment.
- The embedded split terminal currently targets POSIX environments such as Ubuntu/Linux and WSL.
- External-launch behavior includes Linux, macOS, and WSL-aware fallbacks. Native Windows is not a supported runtime for Peneo.
- `config.toml` can override terminal launch commands before those built-in fallbacks are used.
- WSL prefers Windows-side bridges such as `wslview`, `explorer.exe`, and `clip.exe` when available, with Linux-side fallbacks kept for WSLg and desktop Linux environments.
- The application is still under active development, so behavior and keybindings may change.
- File mutations operate on the selected directory entry. If the selected item is a symlink, Peneo mutates the symlink itself instead of silently following and mutating the link target.

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
