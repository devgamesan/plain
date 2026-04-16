# zivo

![CI](https://github.com/devgamesan/zivo/workflows/Python%20CI/badge.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.12+-blue.svg)
![Release](https://img.shields.io/github/v/release/devgamesan/zivo)
![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)

[日本語版 README](README.ja.md)

zivo is a simple and intuitive TUI file manager that lets you browse, search, and operate files without memorizing commands — a Zero-friction Interface for Viewing & Operations.

zivo aims to be usable by everyone without complex configuration, plugin installation, or script creation. It does not aim to do everything — it focuses on making common operations comfortable and simple to perform.

- **No memorization needed**: Common actions are always visible in the help bar
- **Never get lost**: All actions can be called from the command palette
- **Clear 3-pane layout**: Parent, current, and right panes displayed side by side, with text preview for focused files
- **Tabbed browsing**: Keep multiple browser workspaces open inside one TUI and switch between them quickly
- **Embedded terminal**: Seamlessly switch between browsing and shell with `t`
- **Powerful search**: Jump directly to files with recursive file search and grep search
- **Terminal editor integration**: Launch your preferred terminal editor in the current directory
- **External app integration**: Open files directly with their default applications

## Features

- Simple three-pane layout for parent / current / right panes. When the cursor is on a directory, the right pane shows its children. When the cursor is on a common text file, the right pane shows a syntax-highlighted text preview. You can navigate directories, multi-select items, copy, cut, paste, undo recent file operations, move items to trash, delete files, copy paths, rename, create files or directories, extract archives, create zip archives, search for files, run grep searches, and execute one-line shell commands entirely from the keyboard. Common actions stay visible in the help bar at the bottom.

  ![](docs/resources/screen-entire-screen.png)

- Less frequent actions are grouped in the command palette, so you can discover and run them without memorizing every shortcut.

  ![](docs/resources/screen-command-palette.png)

- The beginning of a text file can be previewed directly in the right pane, so you can quickly inspect the file without opening it.

  ![](docs/resources/screen-text-preview.png)

- Multiple tabs let you keep separate working directories open in one zivo session. You can open a new tab, switch to the next or previous tab, and close the current tab without leaving the TUI.

- An embedded terminal can be opened below the browser panes. `t` switches quickly between the browser and terminal, and the terminal starts in the current directory so you can move between browsing and shell work without changing directories manually.

  ![](docs/resources/screen-split-terminal.png)

- Recursive file search makes it easy to jump to the file you want. Just type part of the name to instantly filter through thousands of files and reach your target without drilling through the directory tree manually. Search results also support file preview, making it easy to find what you are looking for.

  ![](docs/resources/screen-find-command.png)

- Recursive grep search is available under the current directory. You can jump from search results directly to the matching file. Context lines around each match can be previewed, making it easy to find what you are looking for. You can also open the matching location directly in a terminal editor.

  ![](docs/resources/screen-grep-command.png)

- Filter input and sort switching are supported. The example below filters by `.py` and sorts by modified time in descending order.

  ![](docs/resources/screen-filter-sort.png)

- Bookmarks let you jump directly to saved directories.

  ![](docs/resources/screen-bookmark.png)

- History lets you jump back to recently visited directories.

  ![](docs/resources/screen-history.png)

- Press `e` on a file to switch into a terminal editor in the current terminal session. Editors such as `nvim`, `vim`, and `nano` can be used seamlessly. The following shows an example of opening Vim from zivo.

  ![](docs/resources/screen-terminal-editor.png)

- Multiple themes are available so you can choose your preferred look.

  ![](docs/resources/screen-theme1.png)

  ![](docs/resources/screen-theme2.png)

- Files and directories can be opened with the OS default application. For example, you can open the current directory in the OS file manager, open a file in VS Code if it is associated on the OS side, or launch an external terminal window rooted at the current directory.

## Supported OS

| OS | Support Status | Notes |
| --- | --- | --- |
| Ubuntu | Supported | Primary verified environment at the moment. |
| Ubuntu (WSL) | Supported | WSL running Ubuntu is part of the verified environments. |
| macOS | Not supported at this time | Some fallback implementations exist, but it is not a formally verified target yet. |
| Windows | Not supported at this time | Native Windows runtime is not supported. |

## Installation

### Prerequisites: Install uv

zivo uses [uv](https://docs.astral.sh/uv/) as the package manager. If you don't have it yet, install it first:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

For other installation methods, see the [uv official documentation](https://docs.astral.sh/uv/getting-started/installation/).

### Install from PyPI

With `uv` installed, install zivo directly from PyPI.

```bash
uv tool install zivo
```

### Install from repository

Alternatively, clone the repository and install zivo as a tool.

```bash
git clone https://github.com/devgamesan/zivo.git
cd zivo
uv tool install --from . zivo
```

To update, pull the latest changes and run the same install command again.

### Dependencies

zivo itself can be installed and started with `uv`, but some features depend on external commands being available on `PATH`. The required tools vary by OS or environment.

#### Ubuntu / Debian

- For grep search (`g`): `ripgrep` (`rg`)
- For copy path (`C`):
  - X11: `xclip`
  - Wayland: `wl-copy`

Install example:

```bash
sudo apt install ripgrep xclip
```

Wayland example:

```bash
sudo apt install ripgrep wl-clipboard
```

#### Ubuntu (WSL)

- For grep search (`g`): `ripgrep` (`rg`)
- For copy path (`C`):
  - `clip.exe` is usually available
  - Linux-side `xclip` / `wl-copy` can also be used when needed
- `wslu` is recommended for GUI bridge commands such as `wslview`

Install example:

```bash
sudo apt install ripgrep wslu
```

#### macOS

- For grep search (`g`): `ripgrep` (`rg`)
- For copy path (`C`): the built-in `pbcopy`

Install example:

```bash
brew install ripgrep
```

#### Windows

- Not supported at this time
- Dependency guidance for native Windows runtime is out of scope

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

Use plain `zivo` when you only want to browse without changing the shell's working directory.

When a file is focused, press `e` to switch into a terminal editor in the current terminal session. zivo prefers `config.toml` `editor.command` when set, then falls back to `$EDITOR`, then built-in defaults such as `nvim`, `vim`, or `nano`.

## Keybindings

### Normal Mode

| Key | Action |
| --- | ------ |
| `j` / `↓` | Move down |
| `PageUp` / `PageDown` | Move cursor by page |
| `k` / `↑` | Move up |
| `Home` / `End` | Jump to first/last visible entry |
| `h` / `←` | Go to parent directory |
| `l` / `→` | Enter directory |
| `Shift+↑` / `Shift+↓` | Extend selection |
| `Enter` | Open file/enter directory |
| `Space` | Toggle selection and move down |
| `a` | Select all visible entries |
| `Esc` | Clear selection / Cancel filter |
| `c` | Copy selected items |
| `x` | Cut selected items |
| `v` | Paste from clipboard |
| `z` | Undo the last reversible file operation |
| `C` | Copy paths to clipboard |
| `r` | Rename selected item |
| `n` | Create new file |
| `N` | Create new directory |
| `Delete` | Move selected items to trash |
| `Shift+Delete` | Permanently delete selected items |
| `i` | Show file attributes |
| `e` | Open file in terminal editor |
| `!` | Execute shell command |
| `f` | Find files (recursive search) |
| `g` | Grep search |
| `/` | Filter files |
| `H` | Show history |
| `b` | Show bookmarks |
| `B` | Toggle current directory bookmark |
| `G` | Go to path |
| `~` | Go to home directory |
| `.` | Toggle hidden files |
| `s` | Cycle sort |
| `d` | Toggle directories-first |
| `R` | Reload directory |
| `t` | Toggle split terminal |
| `T` | Open terminal at current directory |
| `o` | Open new tab |
| `w` | Close current tab |
| `tab` | Switch to next tab |
| `shift+tab` | Switch to previous tab |
| `m` | Open current directory in file manager |
| `:` | Open command palette |
| `q` | Quit |
| `[` | Go back in history |
| `]` | Go forward in history |

### Split Terminal Mode

| Key | Action |
| --- | ------ |
| Any printable character | Send to terminal |
| `Ctrl+v` | Paste from clipboard |
| `Esc` | Close split terminal |

### Input Dialogs

| Key | Action |
| --- | ------ |
| `Enter` | Confirm |
| `Esc` | Cancel |
| `Tab` | Complete (where supported) |
| `Ctrl+v` | Paste from clipboard |

### Search Results Mode (File Search / Grep Search)

| Key | Action |
| --- | ------ |
| `↑` / `↓` | Move cursor through results |
| `Ctrl+n` / `Ctrl+p` | Move cursor down/up through results |
| `PageUp` / `PageDown` | Move cursor by page |
| `Home` / `End` | Jump to first/last result |
| `Enter` | Open selected result |
| `Ctrl+e` | Open selected result in editor |
| `Esc` | Close search |

**Note**: In search results mode, use arrow keys to navigate. `j`/`k` keys are used for typing the search query.

### Filter Mode

| Key | Action |
| --- | ------ |
| Text input | Update filter string |
| `Backspace` | Delete one character |
| `Enter` / `↓` | Apply filter and return to list navigation |
| `Esc` | Clear the filter |

### Command Palette Mode

| Key | Action |
| --- | ------ |
| Text input / `↑` / `↓` / `Ctrl+n` / `Ctrl+p` / `k` / `j` / `Enter` / `Esc` | Filter, select, run, or cancel commands. In `Find files` and `Grep search`, `j` / `k` are treated as text input and result navigation uses `↑` / `↓` or `Ctrl+n` / `Ctrl+p`. |

### Config Editor Mode

| Key | Action |
| --- | ------ |
| `↑` / `↓` / `Ctrl+n` / `Ctrl+p` | Move between settings |
| `←` / `→` / `Enter` | Change the selected value |
| `s` | Save `config.toml` |
| `e` | Open the raw config file in a terminal editor |
| `r` | Reset help bar text to the built-in defaults |
| `Esc` | Close the config editor |

### Name Input Mode

| Key | Action |
| --- | ------ |
| Text input / `Backspace` / `Enter` / `Esc` | Edit, confirm, or cancel rename/create input |

### Confirmation Dialog Mode

| Key | Action |
| --- | ------ |
| `Enter` / `Esc` | Confirm or cancel trash / permanent delete |
| `o` / `s` / `r` / `Esc` | Resolve a paste conflict with overwrite / skip / rename / cancel |

## Command Palette

Less frequent actions are grouped in the command palette opened with `:`.
The tab strip is only shown when two or more browser tabs are open.

| Command | Shown when | Behavior / Notes |
| --- | --- | --- |
| `New tab` | Always | Opens a new browser tab initialized from the current directory. Also available with `o`. |
| `Next tab` | Two or more tabs are open | Activates the next browser tab. Also available with `tab`. |
| `Previous tab` | Two or more tabs are open | Activates the previous browser tab. Also available with `shift+tab`. |
| `Close current tab` | Two or more tabs are open | Closes the active browser tab. The last remaining tab cannot be closed. Also available with `w`. |
| `Find files` | Always | Opens recursive file search. |
| `Grep search` | Always | Opens recursive grep search (`ripgrep` / `rg` required on `PATH`). |
| `History search` | Always | Opens directory history list and jump to a selected directory. |
| `Show bookmarks` | Always | Opens the saved bookmark list and jumps to the selected directory. |
| `Go back` | Directory history has a previous entry | Moves to the previous directory in history. |
| `Go forward` | Directory history has a forward entry | Moves to the next directory in history. |
| `Go to path` | Always | Opens go-to-path input to navigate to a specific path, shows matching directories, and supports `Tab` completion for the selected candidate. |
| `Go to home directory` | Always | Navigates to the home directory. |
| `Reload directory` | Always | Reloads the current directory. |
| `Undo last file operation` | Undo history is not empty | Reverses the most recent undoable rename, paste, or trash operation. Also available with `z`. Trash restore is currently Linux-only. |
| `Toggle split terminal` | Always | Opens or closes the embedded split terminal. |
| `Select all` | Current directory has at least one visible entry | Selects every currently visible entry in the current directory, respecting hidden-file visibility and any active filter. |
| `Show attributes` | Exactly one target is selected or focused | Opens the read-only attribute dialog for the selected item. Also available with `i`. |
| `Rename` | Exactly one target is selected or focused | Starts rename input for a single target. |
| `Compress as zip` | At least one target is selected or focused | Starts zip compression for the selected items, or the focused item when nothing is selected. The destination input accepts absolute and relative paths resolved from the current directory, defaults to a `.zip` path next to the selected content, and asks for confirmation before overwriting an existing zip file. |
| `Extract archive` | Exactly one supported archive file is selected or focused | Starts archive extraction for `.zip`, `.tar`, `.tar.gz`, or `.tar.bz2`. The destination input accepts absolute and relative paths. Relative paths are resolved from the archive file's parent directory, and the default value is a same-name directory next to the archive. Existing destination paths are confirmed before extraction, and the status bar shows entry-count progress while the extraction runs. |
| `Open in editor` | Exactly one file is selected or focused | Opens the focused file in a terminal editor, using `editor.command` -> `$EDITOR` -> built-in defaults. |
| `Copy path` | At least one target is selected or focused | Copies the selected path list, or the focused path when nothing is selected, to the system clipboard. Also available with `C`. |
| `Move to trash` | At least one target is selected or focused | Moves the selected items, or the focused item, to trash (confirmation is enabled by default and can be configured). |
| `Empty trash` | Always (Linux/macOS only) | Permanently deletes all items from the trash. Shows a confirmation dialog before emptying. Not available on Windows. |
| `Open in file manager` | Always | Opens the current directory in the OS file manager. Also available with `m`. |
| `Open terminal` | Always | Launches an external terminal rooted at the current directory, using `config.toml` templates before built-in fallbacks. Also available with `T`. |
| `Run shell command` | Always | Opens a one-line shell command dialog, runs the command in the current directory in the background, and returns the first output line or failure summary in the status bar. Also available with `!`. |
| `Bookmark this directory` / `Remove bookmark` | Always | Saves or removes the current directory in `[bookmarks].paths`. The label reflects whether the current directory is already bookmarked. Also available with `B`. |
| `Show hidden files` / `Hide hidden files` | Always | Toggles hidden-file visibility for the browser panes. The label reflects the current visibility state. Also available with `.`. |
| `Edit config` | Always | Opens the settings overlay for startup defaults. You can edit the preferred terminal editor, hidden-file visibility, directory-size visibility, text preview visibility, theme, sorting, default paste-conflict behavior, and delete confirmation. Theme changes are previewed immediately. Use `↑` / `↓` or `Ctrl+n` / `Ctrl+p` to move, `←` / `→` / `Enter` to change values, `s` to save `config.toml`, and `e` to open the raw config file in a terminal editor. |
| `Create file` | Always | Starts the inline create-file flow in the current directory. |
| `Create directory` | Always | Starts the inline create-directory flow in the current directory. |

## Configuration File

On startup, zivo reads `config.toml` from the platform-specific user config directory.
If the file does not exist yet, zivo creates it automatically with default values.

- Linux: `${XDG_CONFIG_HOME:-~/.config}/zivo/config.toml`
- macOS: `~/Library/Application Support/zivo/config.toml`
- Windows config path is reserved for future compatibility, but native Windows runtime is still unsupported

The supported settings are:

| Section | Key | Values | Description |
| --- | --- | --- | --- |
| `terminal` | `linux` | Array of shell-style command templates | Optional terminal launch commands for Linux. Use `{path}` as the working-directory placeholder. Invalid or empty entries are ignored. |
| `terminal` | `macos` | Array of shell-style command templates | Optional terminal launch commands for macOS, validated the same way as Linux entries. |
| `terminal` | `windows` | Array of shell-style command templates | Optional terminal launch commands for Windows and WSL bridge workflows. The config key is accepted even though native Windows runtime is not currently supported. |
| `editor` | `command` | Shell-style string, for example `nvim -u NONE` | Optional terminal editor command used by `e`. Do not include the file path; zivo appends it automatically. Unsupported GUI editors or invalid commands are ignored. |
| `display` | `show_hidden_files` | `true` / `false` | Default hidden-file visibility when the app starts. |
| `display` | `show_directory_sizes` | `true` / `false` | Shows recursive directory sizes in the current pane. Defaults to `true`. Large directories can be expensive to scan. zivo also calculates sizes automatically while the main pane is sorted by `size`. |
| `display` | `show_preview` | `true` / `false` | Shows the text-file preview in the right pane. Defaults to `true`. Directory and archive child panes are unaffected. grep result context preview follows the same setting. |
| `display` | `show_help_bar` | `true` / `false` | Shows the help bar at the bottom of the screen. Defaults to `true`. The help bar is always shown when the command palette or split terminal is open, regardless of this setting. |
| `display` | `theme` | Any built-in Textual theme, for example `textual-dark`, `textual-light`, `dracula`, or `tokyo-night` | Default UI theme applied on startup. In the settings editor, theme changes are previewed immediately and are persisted when you save. |
| `display` | `preview_syntax_theme` | `auto` or a supported Pygments style, for example `one-dark`, `xcode`, `nord`, or `gruvbox-dark` | Syntax-highlighting colors used by the right-pane text preview. `auto` keeps the current light/dark-based default selection. In the settings editor, changes are previewed immediately when a text preview is visible. |
| `display` | `default_sort_field` | `name` / `modified` / `size` | Default sort field for the main pane. |
| `display` | `default_sort_descending` | `true` / `false` | Starts the main-pane sort in descending order when enabled. |
| `display` | `directories_first` | `true` / `false` | Keeps directories grouped before files in the main pane. |
| `behavior` | `confirm_delete` | `true` / `false` | Shows a confirmation dialog before moving items to trash. Permanent delete via `Shift+Delete` always asks for confirmation. |
| `behavior` | `paste_conflict_action` | `prompt` / `overwrite` / `skip` / `rename` | Chooses the default paste-conflict behavior. `prompt` keeps the conflict dialog enabled. |
| `logging` | `enabled` | `true` / `false` | Enables file output for startup failures and unhandled exceptions. |
| `logging` | `level` | `DEBUG` / `INFO` / `WARNING` / `ERROR` / `CRITICAL` | Log level for file output. Defaults to `ERROR`. Requires app restart to take effect. |
| `logging` | `path` | Path string | Optional log file path. Leave empty to use `zivo.log` next to `config.toml`. Default log file locations: Linux: `~/.config/zivo/zivo.log`, macOS: `~/Library/Application Support/zivo/zivo.log`. |
| `bookmarks` | `paths` | Array of absolute path strings | Bookmarked directories shown by `b` and `Show bookmarks` in the command palette. Duplicate paths are removed when the config is loaded. |

Example:

```toml
[terminal]
linux = ["konsole --working-directory {path}", "gnome-terminal --working-directory={path}"]
macos = ["open -a Terminal {path}"]
windows = ["wt -d {path}"]

[editor]
command = "nvim -u NONE"

[display]
show_hidden_files = false
show_directory_sizes = true
show_preview = true
show_help_bar = true
theme = "textual-dark"
preview_syntax_theme = "auto"
default_sort_field = "name"
default_sort_descending = false
directories_first = true

[behavior]
confirm_delete = true
paste_conflict_action = "prompt"

[logging]
enabled = true
level = "ERROR"
path = ""

[bookmarks]
paths = ["/home/user/src", "/home/user/docs"]
```

Invalid config values do not stop startup. zivo falls back to built-in defaults and shows a warning after the initial directory load.
When logging is enabled, startup failures and unhandled exceptions are appended to the configured log file for later investigation.
The accepted `display.theme` values come from the built-in themes shipped with the installed Textual version.
The accepted `display.preview_syntax_theme` values are `auto` plus the Pygments styles available in the installed environment.

## Notes

- Refer to the "Supported OS" section above for current support status.
- GUI integration such as default-app launch, file-manager launch, and external terminal launch is currently verified mainly on Ubuntu and Ubuntu running under WSL.
- The embedded split terminal currently targets POSIX environments, especially Ubuntu/Linux and WSL.
- `config.toml` can override both the preferred terminal editor and external terminal launch commands before built-in fallbacks are used.
- On WSL, `wslu` is recommended so `wslview` is available for the preferred bridge behavior.
- On WSL, zivo prefers Windows-side bridges such as `wslview`, `explorer.exe`, and `clip.exe` when available, while keeping Linux-side fallbacks for WSLg and desktop Linux environments.
- Behavior and keybindings may change in future revisions.
- File mutations operate on the selected directory entry. If the selected item is a symlink, zivo mutates the symlink itself instead of silently following and mutating the link target.

## Related Documents

- Implementation structure: [docs/architecture.en.md](docs/architecture.en.md)
- Performance notes: [docs/performance.en.md](docs/performance.en.md)

## License

zivo is licensed under the MIT License. See [LICENSE](LICENSE) for details.

### Third-Party Licenses

zivo depends on third-party packages. For a complete list of dependencies and their licenses, see [NOTICE.txt](NOTICE.txt).

To update NOTICE.txt after dependency changes:

```bash
uv run pip-licenses --format=plain --from=mixed --with-urls --output-file NOTICE.txt
```

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
