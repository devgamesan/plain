# Peneo

[日本語版 README](README.ja.md)

Peneo is a Textual-based TUI file manager for environments where you want to keep working in the terminal while still moving smoothly into GUI applications. Its three-pane layout shows the parent, current, and child directories side by side, aiming to feel closer to a GUI file explorer than to a keyboard-heavy power-user tool. Common actions stay visible in the on-screen help, and files can be opened in the OS default app directly from Peneo.

## Features

- Simple three-pane layout for parent / current / child directories. You can navigate directories, multi-select items, copy, cut, paste, move to trash, rename, and create files or directories entirely from the keyboard.
  ![](docs/resources/screen-entire-screen.png)
  _Operating the current directory while keeping surrounding hierarchy visible in the three-pane layout._
- Common actions stay visible in the on-screen help so the interface is easy to pick up without memorizing a large keymap.
  ![](docs/resources/screen-help-bar.png)
  _The help bar at the bottom keeps the main keys visible at all times._
- Less frequent actions are grouped in the command palette.
  ![](docs/resources/screen-command-palette.png)
  _The command palette opened with `:`, showing the main commands._
- An embedded split terminal can be opened below the browser panes. `Ctrl+T` switches quickly between the browser and terminal.
  ![](docs/resources/screen-split-terminal.png)
  _The embedded split terminal opened with `Ctrl+T`, keeping the browser panes visible while shell output stays in view._
- Filter input, recursive file search, and sort switching are supported.
  ![](docs/resources/screen-filter.png)
  _Inline filter input opened with `/`, narrowing the current directory contents in place._
  ![](docs/resources/screen-find-command.png)
  _`Find file` opened from `:`, searching recursively under the current directory._
- File and directory attributes can also be inspected.
  ![](docs/resources/screen-attributes.png)
  _The attribute dialog showing details such as path, size, modified time, and permissions._
- Files can be opened with the OS default app. The current directory can also be handed off to the OS file manager or an external terminal, and `e` can launch a terminal editor in the current terminal session when needed.
  ![](docs/resources/screen-open.png)
  _Operations for opening files with the default app or handing off the current directory to external applications._

## Installation

With `uv` installed, clone the repository and install Peneo as a tool.

```bash
git clone https://github.com/devgamesan/peneo.git
cd peneo
uv tool install --from . peneo
```

On WSL, also install `wslu` so bridge commands such as `wslview` are available:

```bash
sudo apt install wslu
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

`peneo` itself cannot change the current directory of the parent shell. If you want your shell to `cd` into the last directory you visited after quitting Peneo, add the following line to your shell startup file first, such as `.bashrc` or `.zshrc`:

```bash
eval "$(peneo init bash)"  # for bash
eval "$(peneo init zsh)"   # for zsh
```

Open a new shell, or run the same line once in your current shell to enable it immediately. This defines a shell function named `peneo-cd`. After that, launch `peneo-cd` instead of `peneo` when you want the shell directory to follow Peneo on exit:

```bash
peneo-cd
```

Use plain `peneo` or `uv run peneo` when you do not need that behavior.

When a file is focused, press `e` to switch into a terminal editor in the current terminal session. Peneo prefers `config.toml` `editor.command` when set, then falls back to `$EDITOR`, then built-in defaults such as `nvim`, `vim`, or `nano`.

## Configuration File

On startup, Peneo reads `config.toml` from the platform-specific user config directory.
If the file does not exist yet, Peneo creates it automatically with default values.

- Linux: `${XDG_CONFIG_HOME:-~/.config}/peneo/config.toml`
- macOS: `~/Library/Application Support/peneo/config.toml`
- Windows config path is reserved for future compatibility, but native Windows runtime is still unsupported

The supported settings are:

| Section | Key | Values | Description |
| --- | --- | --- | --- |
| `terminal` | `linux` | Array of shell-style command templates | Optional terminal launch commands for Linux. Use `{path}` as the working-directory placeholder. Invalid or empty entries are ignored. |
| `terminal` | `macos` | Array of shell-style command templates | Optional terminal launch commands for macOS, validated the same way as Linux entries. |
| `terminal` | `windows` | Array of shell-style command templates | Optional terminal launch commands for Windows and WSL bridge workflows. The config key is accepted even though native Windows runtime is not currently supported. |
| `editor` | `command` | Shell-style string, for example `nvim -u NONE` | Optional terminal editor command used by `e`. Do not include the file path; Peneo appends it automatically. Unsupported GUI editors or invalid commands are ignored. |
| `display` | `show_hidden_files` | `true` / `false` | Default hidden-file visibility when the app starts. |
| `display` | `theme` | `textual-dark` / `textual-light` | Default UI theme applied on startup and after saving from the settings editor. |
| `display` | `default_sort_field` | `name` / `modified` / `size` | Default sort field for the main pane. |
| `display` | `default_sort_descending` | `true` / `false` | Starts the main-pane sort in descending order when enabled. |
| `display` | `directories_first` | `true` / `false` | Keeps directories grouped before files in the main pane. |
| `behavior` | `confirm_delete` | `true` / `false` | Shows a confirmation dialog before moving items to trash. |
| `behavior` | `paste_conflict_action` | `prompt` / `overwrite` / `skip` / `rename` | Chooses the default paste-conflict behavior. `prompt` keeps the conflict dialog enabled. |

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
theme = "textual-dark"
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
| Normal | `e` | Open the focused file in a terminal editor, using `editor.command` -> `$EDITOR` -> built-in defaults |
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
| Command palette | Text input / `↑` / `↓` / `k` / `j` / `Enter` / `Esc` | Filter, select, run, or cancel commands |
| Split terminal focus | Text input / arrows / `Enter` / `Backspace` / `Esc` / `Tab` | Send input directly to the embedded shell |
| Split terminal focus | `Ctrl+T` | Close the embedded split terminal |
| Name input | Text input / `Backspace` / `Enter` / `Esc` | Edit, confirm, or cancel rename/create input |
| Confirmation dialog | `Enter` / `Esc` | Confirm or cancel delete |
| Confirmation dialog | `o` / `s` / `r` / `Esc` | Resolve a paste conflict with overwrite / skip / rename / cancel |

`e` switches into a terminal editor in the current terminal session rather than opening a separate GUI app window. If both `editor.command` and `$EDITOR` are set, `editor.command` takes precedence.

## Command Palette

Less frequent actions are grouped in the command palette opened with `:`.

| Command | Shown when | Behavior / Notes |
| --- | --- | --- |
| `Find file` | Always | Switches the palette into recursive file-search mode. Plain input searches the current directory tree with a case-insensitive partial basename match. Prefix the query with `re:` to run a Python regular expression against basenames instead; regex is case-sensitive unless you use inline flags such as `(?i)`. Hidden paths are excluded unless hidden files are currently visible, invalid regex patterns are shown inline in the palette, and `Enter` jumps to the selected result by opening its parent directory and focusing that file. |
| `Show attributes` | Exactly one target is selected or focused | Opens a read-only dialog with `Name`, `Type`, `Path`, `Size`, `Modified`, `Hidden`, and `Permissions`. |
| `Copy path` | At least one target is selected or focused | Copies the selected path list, or the focused path when nothing is selected, to the system clipboard. |
| `Open in file manager` | Always | Opens the current directory in the OS file manager. |
| `Open terminal here` | Always | Launches an external terminal rooted at the current directory, using `config.toml` templates before built-in fallbacks. |
| `Open split terminal` / `Close split terminal` | Always | Toggles the embedded split terminal. The label changes with visibility, and the split terminal keeps the directory where it was started instead of following later browser navigation. |
| `Show hidden files` / `Hide hidden files` | Always | Toggles hidden-file visibility for the browser panes. The label reflects the current visibility state. |
| `Edit config` | Always | Opens the settings overlay for startup defaults. You can edit the preferred terminal editor, hidden-file visibility, theme, sorting, default paste-conflict behavior, and delete confirmation. Use `↑` / `↓` to move, `←` / `→` / `Enter` to change values, `s` to save `config.toml`, and `e` to open the raw config file in a terminal editor. |
| `Create file` | Always | Starts the inline create-file flow in the current directory. |
| `Create directory` | Always | Starts the inline create-directory flow in the current directory. |

## Platform Notes

- The project is currently verified on Ubuntu and Ubuntu running under WSL.
- GUI integration paths such as default-app launch, file-manager launch, and terminal launch are currently validated primarily in those environments.
- The embedded split terminal currently targets POSIX environments such as Ubuntu/Linux and WSL.
- External-launch behavior includes Linux, macOS, and WSL-aware fallbacks. Native Windows is not a supported runtime for Peneo.
- `config.toml` can override both the preferred terminal editor and external terminal launch commands before those built-in fallbacks are used.
- On WSL, install `wslu` to make `wslview` available for the preferred bridge behavior.
- WSL prefers Windows-side bridges such as `wslview`, `explorer.exe`, and `clip.exe` when available, with Linux-side fallbacks kept for WSLg and desktop Linux environments.
- Behavior and keybindings may change in future revisions.
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
