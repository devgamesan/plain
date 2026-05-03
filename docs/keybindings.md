# Keybindings

Complete list of keybindings for all zivo modes.

---

## Normal Mode

You can open an external terminal directly from zivo. Press `t` to suspend zivo and open an interactive shell in the current terminal at zivo's current directory. When you exit the shell, zivo resumes automatically. Alternatively, press `T` to launch a separate terminal window.

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
| `d` | Move selected items to trash |
| `D` | Permanently delete selected items |
| `Delete` | Move selected items to trash (fn + Delete on macOS) |
| `Shift+Delete` | Permanently delete selected items (fn + Shift + Delete on macOS) |
| `i` | Show file attributes |
| `e` | Open file in terminal editor |
| `O` | Open file in GUI editor |
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
| `R` | Reload directory |
| `t` | Open terminal in foreground (suspend zivo, open shell in current terminal, resume on exit) |
| `T` | Open terminal at current directory (separate window) |
| `o` | Open new tab |
| `w` | Close current tab |
| `1`-`9`, `0` | Switch to tab 1-9, or tab 10 with `0` |
| `tab` | Switch to next tab |
| `shift+tab` | Switch to previous tab |
| `M` | Open current directory in file manager |
| `:` | Open command palette |
| `q` | Quit |
| `[` | Go back in history |
| `]` | Go forward in history |
| `Ctrl+J` / `Ctrl+↑` | Scroll the right-pane text preview up by a page |
| `Ctrl+K` / `Ctrl+↓` | Scroll the right-pane text preview down by a page |
| `p` | Toggle two-pane transfer mode |

---

## Transfer Mode

| Key | Action |
| --- | ------ |
| `Esc` | Return to normal mode / Clear selection |
| `[` / `]` | Focus the left/right transfer pane |
| `j` / `↓` | Move down in the focused pane |
| `k` / `↑` | Move up in the focused pane |
| `PageUp` / `PageDown` | Move by page in the focused pane |
| `Home` / `End` | Jump to first/last visible entry in the focused pane |
| `h` / `←` | Go to parent directory in the focused pane |
| `~` | Go to home directory in the focused pane |
| `l` / `→` / `Enter` | Enter directory in the focused pane |
| `Space` | Toggle selection and move down in the focused pane |
| `Shift+↑` / `Shift+↓` | Extend selection in the focused pane |
| `a` | Select all visible entries in the focused pane |
| `c` | Copy selected items to clipboard |
| `x` | Cut selected items to clipboard |
| `v` | Paste from clipboard to focused pane |
| `y` | Copy focused-pane targets to opposite pane (copy-to-pane) |
| `m` | Move focused-pane targets to opposite pane (move-to-pane) |
| `d` | Delete focused-pane targets to trash |
| `r` | Rename focused or single selected entry |
| `z` | Undo the last file operation |
| `.` | Toggle hidden files |
| `N` | Create new directory in the focused pane |
| `b` | Show bookmarks |
| `H` | Show history |
| `:` | Open a transfer-mode command palette with transfer-available commands only |
| `o` | Open new tab |
| `w` | Close current tab |
| `1`-`9`, `0` | Switch to tab 1-9, or tab 10 with `0` |
| `tab` | Switch to next tab |
| `shift+tab` | Switch to previous tab |
| `p` / `Esc` | Return to normal mode |
| `q` | Exit the application |

---

## Input Dialogs

| Key | Action |
| --- | ------ |
| `Enter` | Confirm |
| `Esc` | Cancel |
| `Tab` | Complete (where supported) |
| `Ctrl+v` | Paste from clipboard |

---

## Search Results Mode (File Search / Grep Search)

| Key | Action |
| --- | ------ |
| `↑` / `↓` | Move cursor through results |
| `Ctrl+j` / `Ctrl+k` | Move cursor down/up through results |
| `PageUp` / `PageDown` | Move cursor by page |
| `Home` / `End` | Jump to first/last result |
| `Enter` | Open selected result |
| `Ctrl+e` | Open selected result in editor |
| `Ctrl+o` | Open selected result in GUI editor |
| `Esc` | Close search |

**Note**: In search results mode, use arrow keys or `Ctrl+j`/`Ctrl+k` to navigate. `j`/`k` keys are used for typing the search query.

---

## Filter Mode

| Key | Action |
| --- | ------ |
| Text input | Update filter string |
| `Backspace` | Delete one character |
| `Enter` / `↓` | Apply filter and return to list navigation |
| `Esc` | Clear the filter |

---

## Command Palette Mode

| Key | Action |
| --- | ------ |
| Text input / `↑` / `↓` / `Ctrl+j` / `Ctrl+k` / `k` / `j` / `Enter` / `Esc` | Filter, select, run, or cancel commands. In `Find files` and `Grep search`, `j` / `k` are treated as text input and result navigation uses `↑` / `↓` or `Ctrl+j` / `Ctrl+k`. |

When the `Replace text` preview is open in the right pane, `Shift+↑` / `Shift+↓` scroll that preview.

---

## Config Editor Mode

| Key | Action |
| --- | ------ |
| `↑` / `↓` / `Ctrl+j` / `Ctrl+k` | Move between settings |
| `←` / `→` / `Enter` | Change the selected value |
| `s` | Save `config.toml` |
| `e` | Open the raw config file in a terminal editor |
| `r` | Reset help bar text to the built-in defaults |
| `Esc` | Close the config editor |

---

## Name Input Mode

| Key | Action |
| --- | ------ |
| Text input / `Backspace` / `Enter` / `Esc` | Edit, confirm, or cancel rename/create input |

---

## Confirmation Dialog Mode

| Key | Action |
| --- | ------ |
| `Enter` / `Esc` | Confirm or cancel trash / permanent delete |
| `o` / `s` / `r` / `Esc` | Resolve a paste conflict with overwrite / skip / rename / cancel |
