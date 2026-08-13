# Keybindings

Complete list of keybindings for all zivo modes.

## Help Bar

The three-row help bar keeps a stable order. Browsing uses these groups:

1. `enter open`, `e edit`, `/ filter`, `s sort`, `. hidden`, `[ ] bk/fwd`, `q quit`
2. `space select`, `c copy`, `x cut`, `v paste`, `d trash`, `r rename`, `z undo`
3. `f find`, `g grep`, `G go`, `n new-file`, `N new-dir`, `t term`, `: palette`

Search Workspace shows `enter open`, `e edit`, `/ filter`, `s sort`, `. hidden`, `[ ] bk/fwd`, `q quit`, then `space select`, `c copy`, `z undo`, and `: palette`.

On terminals narrower than 80 columns, normal browsing uses `Tab` to toggle the details view (preview/results) and the current file list. The current cursor, selection, filter, and preview identity are preserved; `j` / `k` still move the underlying current-list cursor. Search Workspace keeps `Tab` for moving between its input fields.

Transfer shows `enter dir`, `. hidden`, `Tab switch-pane`, `p/Esc close`, `q quit`, then `space select`, `c copy-to-pane`, `m move-to-pane`, `d trash`, `r rename`, `z undo`, and finally `G go`, `N new-dir`, `: palette`. `D` remains documented below but is intentionally omitted from the help bar.

When a text preview is active, drag to select text, then press `c` or click `Copy selection` in the preview footer. `Esc` clears an active preview selection. The footer also shows `Ctrl+J/K scroll preview`. Replace previews use `Shift+↑/↓ scroll preview`; `Ctrl+↑/↓` are aliases for normal preview scrolling. Image and other non-text previews do not support text selection. Narrow terminals keep three rows and elide lower-frequency items from the right.

Mouse affordances mirror these actions: click breadcrumb segments or normal-browsing Back/Forward controls to navigate, click a tab to activate it, hover a tab for `×` close, use `+` for a new tab, and click the Name/Size/Modified headers to sort. Search Workspace is shown as a dedicated label, and Transfer mode does not add path-bar history buttons.

---

## Normal Mode

Press `!` for a short non-interactive command or `t` to suspend zivo and work interactively in a foreground shell. Use the `:` command palette for external application launches and other lower-frequency actions. The foreground shell starts in zivo's current directory and zivo resumes when you exit it.

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
| `c` | Copy selected preview text when a text range is active; otherwise copy selected (or focused) filesystem items |
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
| `G` | Open the unified Go view |
| `/` | Filter files |
| `b` | Open the Go view filtered to bookmarks |
| `~` | Go to home directory |
| `.` | Toggle hidden files |
| `s` | Cycle sort |
| `t` | Open foreground shell (suspend zivo, open interactive shell in current terminal, resume on exit) |
| `o` | Open new tab |
| `w` | Close current tab |
| `1`-`9`, `0` | Switch to tab 1-9, or tab 10 with `0` |
| `:` | Open command palette |
| `q` | Quit |
| `[` | Go back in history |
| `]` | Go forward in history |
| `Ctrl+J` / `Ctrl+↑` | Scroll the right-pane text preview up by a page |
| `Ctrl+K` / `Ctrl+↓` | Scroll the right-pane text preview down by a page |
| `p` | Toggle two-pane transfer mode |
| `Tab` (under 80 columns) | Toggle between the current file list and the details view (preview/results) |

---

## Transfer Mode

The active pane is the source and the opposite pane is the destination; the direction and counts are shown in the header. Clipboard cut/copy/paste (`c`/`x`/`v`) are normal-mode only.

| Key | Action |
| --- | ------ |
| `Tab` / `Shift+Tab` | Switch focus to the opposite pane (sets transfer direction) |
| `1`-`9`, `0` | Switch to tab 1-9, or tab 10 with `0` |
| `Esc` | Clear selection, or return to normal mode when nothing is selected |
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
| `c` | Copy selected (or focused) items to the opposite pane |
| `m` | Move selected (or focused) items to the opposite pane |
| `d` | Delete focused-pane targets to trash |
| `D` | Permanently delete focused-pane targets |
| `Delete` / `Shift+Delete` | Move to trash / permanently delete |
| `r` | Rename focused or single selected entry |
| `z` | Undo the last file operation |
| `.` | Toggle hidden files |
| `N` | Create new directory in the focused pane |
| `b` | Open the Go view filtered to bookmarks |
| `G` | Open the unified Go view for the active pane |
| `:` | Open a transfer-mode command palette (new/rename/delete/tabs/etc.) |
| `p` | Return to normal mode |
| `q` | Exit the application |

Browser tab operations are reachable from the transfer-mode command palette (`:`); switch tabs directly with number keys `1`-`9`/`0`. `Tab` switches panes.

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
| Text input / `↑` / `↓` / `Ctrl+j` / `Ctrl+k` / `k` / `j` / `Enter` / `Esc` | Filter, select, run, or cancel commands. In `Find files`, `Grep search`, and `Replace text`, `j` / `k` are treated as text input; result navigation uses `↑` / `↓` or `Ctrl+j` / `Ctrl+k`. |

While Find files or Grep search results are displayed, `Ctrl+r` (or the clickable `Replace results` footer) passes the displayed file results into the unified replacement preview.

When the `Replace text` preview is open in the right pane, `Shift+↑` / `Shift+↓` scroll that preview.

---

## Config Editor Mode

| Key | Action |
| --- | ------ |
| `↑` / `↓` / `Ctrl+j` / `Ctrl+k` | Move between settings |
| `←` / `→` / `Enter` | Change the selected value |
| `s` | Save `config.toml` |
| `e` | Open `config.toml` to edit advanced settings in a terminal editor; save or close pending Config Editor changes first |
| `Esc` | Close the config editor |

---

## Name Input Mode

| Key | Action |
| --- | ------ |
| Text input / `Backspace` / `Enter` / `Esc` | Edit, confirm, or cancel rename/create input |

## Bulk Rename Mode

Bulk rename opens with `Base name` active. Entering a base name fills the review table with numbered names while preserving each original extension (`project_1.txt`, `project_2.md`). Press `r` or choose `Rename N items` with multiple selections.

| Key | Behavior |
| --- | --- |
| Text input / `Backspace` | Edit the Base name and regenerate all New Name values |
| `Enter` | Run `Rename items` |
| `Ctrl+V` | Paste clipboard text into the Base name |
| `Esc` | Close the overlay and discard the draft |

There is only one keyboard input field in this mode, so `Tab` / `Shift+Tab` do not move focus to another control.

---

## Confirmation Dialog Mode

| Key | Action |
| --- | ------ |
| `Enter` / `Esc` | Confirm or cancel Move to trash and single-file Permanently delete |
| `Enter` then `D` | Two-step confirmation for multiple targets or directories |
| `o` / `s` / `r` / `Esc` | Resolve a paste conflict with overwrite / skip / rename / cancel |

The direct keys `i`, `C`, `B`, `M`, `O`, `T`, `H`, and `R` are intentionally unbound. Their attribute, path-copy, bookmark, navigation, external-launch, history, and reload commands remain available from the command palette. `G` is reserved for the unified Go view.

## Long-running Operation Mode

While Copy, Move, Compress, Extract, or Replace is running, normal browsing, directory navigation, file search, preview, and attribute inspection remain available. When the active service supports safe cancellation, press `Esc` in normal browsing or Transfer mode, or click `Cancel` in the status bar. `Esc` in dialogs, the command palette, and input forms keeps its existing local meaning. Other file mutations, Undo, editor or shell launches, and mutation-capable custom actions are rejected with the active operation name. The current item finishes before the operation stops; after a cancel request, repeated cancellation is ignored.
