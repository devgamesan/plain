# Command Palette

Complete list of commands available in the command palette, opened with `:`.
Lower-frequency attribute, path-copy, bookmark-edit, external-launch, and reload actions are intentionally available here. Destination navigation is handled by the unified `Go` command, while `~`, `[`, `]`, and `b` remain quick paths.
In transfer mode, the command palette only shows commands that are available for the active transfer pane.
The tab strip is only shown when two or more browser tabs are open.

When the query is empty, the palette shows the fixed `Navigate`, `File`, `Search`, `View`, `System`, and `Custom actions` sections. Category order and command ranking are deterministic and do not use usage history or telemetry.

The complete command list is scrollable with the mouse wheel. Keyboard cursor movement (`↑` / `↓` or `Ctrl+j` / `Ctrl+k`) automatically keeps the selected row visible.

Search also matches command keywords and common aliases. Exact label matches rank first, followed by label prefixes, word prefixes, partial matches, and deterministic fuzzy matches. Disabled commands remain searchable and show a concrete reason; pressing Enter reports the same reason without executing the command. Custom actions remain governed by their configured context conditions and are searchable by name.

| Command | Shown when | Behavior / Notes |
| --- | --- | --- |
| `New tab` | Always | Opens a new browser tab initialized from the current directory. |
| `Next tab` | Two or more tabs are open | Activates the next browser tab. |
| `Previous tab` | Two or more tabs are open | Activates the previous browser tab. |
| `Close current tab` | Two or more tabs are open | Closes the active browser tab. The last remaining tab cannot be closed. |
| `Find files` | Always | Opens recursive file search. |
| `Grep search` | Always | Opens the shared recursive content search (`ripgrep` / `rg` required on `PATH`). The legacy phrase `search contents` is also a search alias. Choose current directory, selected files/directories, or Search Workspace (available only while browsing one); keyword, filename, include-extension, and exclude-extension filters are available in every scope. Selected directories are searched recursively. |
| `Go` | Always | Searches Home, bookmarks, recent history, open tabs, and direct paths in one view. Use `@bookmark`, `@history` / `@recent`, `@tab`, or `@home` at the start of the query to limit the source. `b` opens the same view limited to bookmarks. `j` and `k` are ordinary query characters; use arrow keys or `Ctrl+j` / `Ctrl+k` to move the selection. |
| `Go back` | Directory history has a previous entry | Moves to the previous directory in history. |
| `Go forward` | Directory history has a forward entry | Moves to the next directory in history. |
| `Go to home directory` | Always | Navigates to the home directory. |
| `Reload directory` | Always | Reloads the current directory. |
| `Toggle transfer mode` / `Close transfer mode` | Always | Switches between the normal three-pane browser and the two-pane transfer layout. |
| `Undo last file operation` | Undo history is not empty | Reverses the most recent undoable rename, paste, or trash operation. |
| `Select all` | Current directory has at least one visible entry | Selects every currently visible entry in the current directory, respecting hidden-file visibility and any active filter. |
| `Save results` | Grep search results are shown | Saves the current grep results to `grep_results.txt` in the current directory, including the configured grep preview context lines. Existing files are left unchanged. |
| `Replace text` | Always | Opens one scope-aware replacement palette. Scope is initially Selected files, Current file, or Current directory according to the current selection. Select Current file, Selected files, Current directory, Found files, or Grep result files; unavailable scopes explain why. Find/Replace is always shown, while filename and extension filters are shown when the scope searches recursively. The right pane shows a diff preview before confirmation. |
| `Show attributes` | Exactly one target is selected or focused | Opens the read-only attribute dialog for the selected item. |
| `Rename` | Exactly one target is selected or focused | Starts rename input for a single target. |
| `Change permissions` | One or more targets are selected or focused in a real filesystem workspace on Linux, macOS, or WSL | Starts permission input for the selected targets, or the focused target when nothing is selected. Enter a three-digit octal mode such as `755` or `644`. The dialog shows target count/types and that symlinks are skipped and never followed. `Recursive` defaults to `No`; press `Tab` to choose `Yes` and include directory descendants. This command is hidden in search workspaces and native Windows because Windows does not expose POSIX permission bits through `chmod`. |
| `Change owner` | One or more targets are selected or focused in a real filesystem workspace on Linux, macOS, or WSL | Starts owner/group input for the selected targets, or the focused target when nothing is selected. Enter `owner`, `owner:group`, or `:group`. The dialog shows target count/types and that symlinks are skipped and never followed. `Recursive` defaults to `No`; press `Tab` to choose `Yes` and include directory descendants. This command is hidden in search workspaces and native Windows. |
| `Compress as zip` | At least one target is selected or focused | Starts zip compression for the selected items, or the focused item when nothing is selected. The destination input accepts absolute and relative paths resolved from the current directory, defaults to a `.zip` path next to the selected content, and asks for confirmation before overwriting an existing zip file. |
| `Extract archive` | Exactly one supported archive file is selected or focused | Starts archive extraction for `.zip`, `.tar`, `.tar.gz`, or `.tar.bz2`. The destination input accepts absolute and relative paths. Relative paths are resolved from the archive file's parent directory, and the default value is a same-name directory next to the archive. Existing destination paths are confirmed before extraction, and the status bar shows entry-count progress while the extraction runs. |
| `Open` | Exactly one file is selected or focused | Opens the focused file with its OS default application. |
| `Edit with terminal editor` | Exactly one file is selected or focused | Opens the focused file in a terminal editor, using `editor.command` -> `$EDITOR` -> built-in defaults. |
| `Edit with GUI editor` | Exactly one file is selected or focused | Opens the focused file in a configured GUI editor. |
| `Copy path` | At least one target is selected or focused | Copies the selected path list, or the focused path when nothing is selected, to the system clipboard. |
| `Move to trash` | At least one target is selected or focused | Moves the selected items, or the focused item, to trash (confirmation is enabled by default and can be configured). On Windows this uses the Recycle Bin via `send2trash`. |
| `Open current directory with file manager` | Always | Opens the current directory in the OS file manager. |
| `Open current directory with terminal` | Always | Launches a separate terminal window rooted at zivo's current directory, using `config.toml` templates before built-in fallbacks. Use this for independent or longer-running work. |
| `Run shell command` | Always | Opens a one-line command dialog and runs a short, non-interactive command in the current directory in the background. The dialog shows its cwd; results retain exit code, stdout, and stderr. Press `r` to rerun or `t` to open that cwd in an external terminal. For interactive commands, use foreground shell (`t` from browsing) instead. On Windows, zivo prefers `powershell.exe`, then `pwsh`, then `cmd.exe`, so syntax follows the selected Windows shell rather than POSIX `sh`. |
| Custom actions | Every configured `[[actions.custom]]` entry (entries that do not match `when` or `extensions` are disabled) | Shows reusable named entries from `[[actions.custom]]` in `config.toml`. zivo confirms the expanded command before running it. Use `background` for repeatable non-interactive tasks, `terminal` for interactive tasks, and `terminal_window` for independent work. See [Custom Actions](custom-actions.md). |
| `Bookmark this directory` / `Remove bookmark` | Always | Saves or removes the current directory in `[bookmarks].paths`. The label reflects whether the current directory is already bookmarked. |
| `Show hidden files` / `Hide hidden files` | Always | Toggles hidden-file visibility for the browser panes. The label reflects the current visibility state. |
| `Edit config` | Always | Opens the settings overlay for startup defaults. You can edit the preferred terminal editor, GUI editor preset, external terminal launch mode, hidden-file visibility, directory-size visibility, text preview visibility, image preview visibility, image preview mode, PDF preview visibility, Office preview visibility, preview size limit, theme, sorting, default paste-conflict behavior, and delete confirmation. The overlay also explains what the selected setting changes so you do not need to cross-reference the README while browsing options. Theme changes are previewed immediately. |
| `Create file` | Always | Starts the inline create-file flow in the current directory. |
| `Create directory` | Always | Starts the inline create-directory flow in the current directory. |
