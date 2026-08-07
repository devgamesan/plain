# Keybindings

Complete list of keybindings for all zivo modes.

---

## Normal Mode

Press `!` for a short non-interactive command or `t` to suspend zivo and work interactively in a foreground shell. Use the `:` command palette for external application launches and other lower-frequency actions. The foreground shell starts in zivo's current directory and zivo resumes when you exit it.

### Contextual help bar

The help bar has two rows. The contextual row shows up to five target-focused actions, or six when the sixth item is a trailing `Paste` action, while the discovery row keeps common feature entry points visible:

```text
enter Open | e Edit | space Select | c Copy | x Cut
/ Filter | f Find | g Grep | q Quit | : Commands
```

| State | Primary actions |
| --- | --- |
| File under cursor | `Enter Open`, `e Edit`, `Space Select`, `c Copy`, `x Cut` |
| Directory under cursor | `Enter Open dir`, `Space Select`, `c Copy`, `x Cut` |
| One or more selected | `c Copy`, `x Cut`, `d Move to trash`, `r Rename`, `Esc Clear selection` |
| Clipboard available | `v Paste` is shown last when it fits; otherwise use `: Commands` |
| Empty directory | `n New file`, `N New directory`, and `v Paste` when available |

In Search Workspace, the discovery row uses `Filter`, `Sort`, `Show hidden`/`Hide hidden`, `Quit`, and `: Commands`, because Find/Grep and destructive transfer actions are unavailable there. Transfer mode uses pane focus and copy/move-to-pane actions in the discovery row. Pressing `:` or clicking `: Commands` opens the existing command palette. Clicking any other item sends the same action through the central dispatcher as its keyboard shortcut. Dialogs show only their own confirm/apply and cancel actions.

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
| `r` | Rename selected item |
| `n` | Open Create with File selected |
| `N` | Open Create with Directory selected |
| `d` | Move selected items to trash |
| `D` | Permanently delete selected items |
| `Delete` | Move selected items to trash (fn + Delete on macOS) |
| `Shift+Delete` | Permanently delete selected items (fn + Shift + Delete on macOS) |
| `e` | Edit selected file with terminal editor |
| `!` | Run a short non-interactive shell command in the current directory; the dialog shows cwd and retains output/error details |
| `f` | Find files (recursive search) |
| `g` | Grep search |
| `/` | Filter files |
| `b` | Open the Go view filtered to bookmarks |
| `~` | Go to home directory |
| `.` | Toggle hidden files |
| `s` | Cycle sort |
| `t` | Open foreground shell (suspend zivo, open interactive shell in current terminal, resume on exit) |
| `o` | Open new tab |
| `w` | Close current tab |
| `1`-`9`, `0` | Switch to tab 1-9, or tab 10 with `0` |
| `tab` | Switch to next tab |
| `shift+tab` | Switch to previous tab |
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
| `D` | Permanently delete focused-pane targets |
| `Delete` / `Shift+Delete` | Move to trash / permanently delete |
| `r` | Rename focused or single selected entry |
| `z` | Undo the last file operation |
| `.` | Toggle hidden files |
| `N` | Create new directory in the focused pane |
| `b` | Open the Go view filtered to bookmarks |
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
| `Tab` | Toggle `Recursive: No/Yes` in Change permissions / Change owner dialogs |

---

## Search Results Mode (File Search / Grep Search)

| Key | Action |
| --- | ------ |
| `↑` / `↓` | Move cursor through results |
| `Ctrl+j` / `Ctrl+k` | Move cursor down/up through results |
| `PageUp` / `PageDown` | Move cursor by page |
| `Home` / `End` | Jump to first/last result |
| `Enter` | Open selected result |
| `Ctrl+e` | Edit selected result with terminal editor |
| `Ctrl+o` | Edit selected result with GUI editor |
| `Ctrl+x` | Save grep results to `grep_results.txt` in the current directory, including the configured context lines. |
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
| `e` | Open `config.toml` to edit advanced settings in a terminal editor |
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
| `Enter` / `Esc` | Confirm or cancel trash and single-file permanent delete |
| `Enter` then `D` | Two-step confirmation for multiple targets or directories |
| `o` / `s` / `r` / `Esc` | Resolve a paste conflict with overwrite / skip / rename / cancel |

The direct keys `i`, `C`, `B`, `G`, `M`, `O`, `T`, `H`, and `R` are intentionally unbound. Their attribute, path-copy, bookmark, navigation, external-launch, history, and reload commands remain available from the command palette.
