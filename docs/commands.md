# Command Palette

Complete list of commands available in the command palette, opened with `:`.
In transfer mode, the command palette only shows commands that are available for the active transfer pane.
The tab strip is only shown when two or more browser tabs are open.

| Command | Shown when | Behavior / Notes |
| --- | --- | --- |
| `New tab` | Always | Opens a new browser tab initialized from the current directory. Also available with `o`. |
| `Next tab` | Two or more tabs are open | Activates the next browser tab. Also available with `tab`. |
| `Previous tab` | Two or more tabs are open | Activates the previous browser tab. Also available with `shift+tab`. |
| `Close current tab` | Two or more tabs are open | Closes the active browser tab. The last remaining tab cannot be closed. Also available with `w`. |
| `Find files` | Always | Opens recursive file search. |
| `Grep search` | Always | Opens recursive grep search (`ripgrep` / `rg` required on `PATH`) with keyword, filename, include-extension, and exclude-extension filters. |
| `Grep in selected files` | A file is focused or one or more files are selected in the current directory | Opens grep search limited to the selected files, or the focused file when nothing is explicitly selected. Type a keyword to search within those files via grep, and matching lines appear in the palette. Use `↑` / `↓` or `Ctrl+n` / `Ctrl+p` to move between results, `Enter` to navigate to the file, `Ctrl+e` to open the file in a terminal editor, and `Ctrl+o` to open the matching location in a GUI editor. |
| `History search` | Always | Opens directory history list and jump to a selected directory. |
| `Show bookmarks` | Always | Opens the saved bookmark list and jumps to the selected directory. |
| `Go back` | Directory history has a previous entry | Moves to the previous directory in history. |
| `Go forward` | Directory history has a forward entry | Moves to the next directory in history. |
| `Go to path` | Always | Opens go-to-path input to navigate to a specific path, shows matching directories, and supports `Tab` completion for the selected candidate. On native Windows, drive roots are also offered so you can switch between drives quickly. |
| `Go to home directory` | Always | Navigates to the home directory. |
| `Reload directory` | Always | Reloads the current directory. |
| `Toggle transfer mode` / `Close transfer mode` | Always | Switches between the normal three-pane browser and the two-pane transfer layout. Also available with `p` from normal mode, and `p` / `Esc` while transfer mode is open. |
| `Undo last file operation` | Undo history is not empty | Reverses the most recent undoable rename, paste, or trash operation. Also available with `z`. |
| `Select all` | Current directory has at least one visible entry | Selects every currently visible entry in the current directory, respecting hidden-file visibility and any active filter. |
| `Replace text in selected files` | A file is focused or one or more files are selected in the current directory | Opens a two-field replacement palette for the selected files, or the focused file when nothing is explicitly selected. Matching files appear in the palette, `↑↓` and `Ctrl+n` / `Ctrl+p` move between them, and the right pane shows the selected file's diff before `Enter` applies the replacement. `Shift+↑` / `Shift+↓` scrolls the diff preview. |
| `Replace text in found files` | Always | Opens a three-field replacement palette (filename, find, replace). Type a filename pattern to search for files, then type find/replace text to preview replacements. `Tab` / `Shift+Tab` cycle between fields. The right pane shows the diff preview, and `Enter` applies the replacement. |
| `Replace text in grep results` | Always | Opens a five-field replacement palette (keyword, replace, filename filter, include extensions, exclude extensions). The keyword is both the grep search term and the text to replace. Type a keyword to grep search, then type a replacement to preview changes. Optional filename and extension filters narrow which matched files are affected. `Tab` / `Shift+Tab` cycle between fields. The right pane shows the diff preview, and `Enter` applies the replacement. |
| `Grep and replace in selected files` | A file is focused or one or more files are selected in the current directory | Opens a two-field replacement palette (keyword, replace) for the selected files, or the focused file when nothing is explicitly selected. The keyword searches within those files via grep, matching lines appear in the palette, and the right pane shows the selected file's diff before `Enter` applies the replacement. `Tab` / `Shift+Tab` cycle between fields. |
| `Show attributes` | Exactly one target is selected or focused | Opens the read-only attribute dialog for the selected item. Also available with `i`. |
| `Rename` | Exactly one target is selected or focused | Starts rename input for a single target. |
| `Compress as zip` | At least one target is selected or focused | Starts zip compression for the selected items, or the focused item when nothing is selected. The destination input accepts absolute and relative paths resolved from the current directory, defaults to a `.zip` path next to the selected content, and asks for confirmation before overwriting an existing zip file. |
| `Extract archive` | Exactly one supported archive file is selected or focused | Starts archive extraction for `.zip`, `.tar`, `.tar.gz`, or `.tar.bz2`. The destination input accepts absolute and relative paths. Relative paths are resolved from the archive file's parent directory, and the default value is a same-name directory next to the archive. Existing destination paths are confirmed before extraction, and the status bar shows entry-count progress while the extraction runs. |
| `Open in editor` | Exactly one file is selected or focused | Opens the focused file in a terminal editor, using `editor.command` -> `$EDITOR` -> built-in defaults. |
| `Open in GUI editor` | Exactly one file is selected or focused | Opens the focused file in a configured GUI editor. Also available with `O`. |
| `Copy path` | At least one target is selected or focused | Copies the selected path list, or the focused path when nothing is selected, to the system clipboard. Also available with `C`. |
| `Move to trash` | At least one target is selected or focused | Moves the selected items, or the focused item, to trash (confirmation is enabled by default and can be configured). On Windows this uses the Recycle Bin via `send2trash`. |
| `Empty trash` | Always | Permanently deletes all items from the trash. Shows a confirmation dialog before emptying. On Windows this uses PowerShell's `Clear-RecycleBin` to empty the Recycle Bin. |
| `Open in file manager` | Always | Opens the current directory in the OS file manager. Also available with `M`. |
| `Open current directory in GUI editor` | Always | Opens zivo's current directory in the configured GUI editor. |
| `Open terminal` | Always | Launches an external terminal rooted at zivo's current directory, using `config.toml` templates before built-in fallbacks. Also available with `T` and `t`. |
| `Run shell command` | Always | Opens a one-line shell command dialog, runs the command in the current directory in the background, and returns the first output line or failure summary in the status bar. On Windows, zivo prefers `powershell.exe`, then `pwsh`, then `cmd.exe`, so command syntax follows the selected Windows shell rather than POSIX `sh`. Also available with `!`. |
| `Bookmark this directory` / `Remove bookmark` | Always | Saves or removes the current directory in `[bookmarks].paths`. The label reflects whether the current directory is already bookmarked. Also available with `B`. |
| `Show hidden files` / `Hide hidden files` | Always | Toggles hidden-file visibility for the browser panes. The label reflects the current visibility state. Also available with `.`. |
| `Edit config` | Always | Opens the settings overlay for startup defaults. You can edit the preferred terminal editor, GUI editor preset, external terminal launch mode, hidden-file visibility, directory-size visibility, text preview visibility, image preview visibility, PDF preview visibility, Office preview visibility, preview size limit, theme, sorting, default paste-conflict behavior, and delete confirmation. The overlay also explains what the selected setting changes so you do not need to cross-reference the README while browsing options. Theme changes are previewed immediately. Use `↑` / `↓` or `Ctrl+n` / `Ctrl+p` to move, `←` / `→` / `Enter` to change values, `s` to save `config.toml`, and `e` to open the raw config file in a terminal editor. |
| `Create file` | Always | Starts the inline create-file flow in the current directory. |
| `Create directory` | Always | Starts the inline create-directory flow in the current directory. |
