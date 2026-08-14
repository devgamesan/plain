# Safety

zivo includes several safety mechanisms to prevent accidents during file operations.

> Audience: users reviewing the confirmation, trash, undo, and recovery behavior before operating on files.

---

## Move to trash

- Press `d` or `Delete` to move selected items to the trash.
- A confirmation dialog is shown by default (configurable via `behavior.confirm_delete` in `config.toml`).
- On macOS and Linux, items are moved to the OS standard trash via `send2trash`.
- On Windows, items are moved to the Recycle Bin via `send2trash`.

---

## Permanently Delete

- Press `D` or `Shift+Delete` to permanently delete selected items.
- Permanently delete always asks for confirmation regardless of the `behavior.confirm_delete` setting.
- The confirmation shows the target count, total size, up to three representative names, and whether any sizes could not be read.
- Multiple targets or any directory require two explicit steps: press `Enter` to review, then uppercase `D` to delete.
- Unlike Move to trash, this operation cannot be undone.

---

## Undo

- Press `z` to undo the most recent file operation.
- Undoable operations: rename, paste (including cross-pane Copy/Move in Transfer mode), duplicate, and move to trash.
- `Undo last file operation` is hidden from the command palette when the undo history is empty.
- Only reversible file operations are recorded in the undo history.

## Bulk Rename

- Selecting two or more items and invoking `r` or `Rename selected items` opens a review overlay with a Base name input, Old Name / New Name / Status rows, and a count summary before any filesystem change.
- The Base name generates numbered destinations while preserving each original extension. Unchanged rows are skipped. Any collision, invalid name, missing target, or parent-directory permission failure disables the apply action.
- Execution stages entries under temporary names in the same directory before applying final names, so cycles such as `a→b` and `b→a` are safe. Failures trigger best-effort rollback and remain visible per row.
- A single Undo entry is recorded only after every changed row succeeds. Undo also stages through temporary names and does not create history for a partial result.

---

## Paste Conflict Resolution

- When the paste destination already contains a file with the same name (including the opposite pane during a Transfer-mode Copy/Move), a conflict dialog is shown.
- Choose from `o` (overwrite), `s` (skip), `r` (rename), or `Esc` (cancel).
- The default behavior is configurable via `behavior.paste_conflict_action` in `config.toml`.

---

## Symlink Operations

- File mutations operate on the selected directory entry itself.
- If the selected item is a symlink, zivo mutates the symlink itself instead of silently following and mutating the link target.

---

## Text Replacement Preview

- Before applying batch text replacements, a diff preview is shown in the right pane.
- Find/Grep/Search Workspace results enter replacement through an explicit `Search results` target; the preview identifies the source and file/match counts.
- Press `Enter` to confirm the replacement after reviewing changes.
- Use `Shift+↑` / `Shift+↓` to scroll the diff preview.

---

## Archive Extraction Safety

- If the destination already exists, a confirmation dialog is shown before extraction.
- The status bar shows entry-count progress while the extraction runs.
- Before writing, zivo normalizes the destination lexically and inspects the destination root and every target path component with `lstat()`.
- Existing symlinks and Windows reparse points in the destination root, its parents, or an extracted target are rejected with an unsafe-path error; absolute and `..` archive members are rejected as well.
- All archive targets are validated before the first write, and the containment check is repeated before directory creation and atomic file replacement. This applies to ZIP, TAR, GZ, and BZ2 extraction.

## Long-Running File Operations

- Copy, Move, Compress, Extract, and Replace show the operation name, progress, and current target without locking normal browsing. Directory navigation, file search, preview, and attribute inspection remain available.
- Long-running file operations are serialized. Other file mutations, Undo, editor or shell launches, and mutation-capable custom actions are rejected with the active operation name.
- `Cancel` and `Esc` request cooperative cancellation only at safe item boundaries; the current item is allowed to finish and workers are never force-stopped.
- An exit request asks for cancellation and exits only after the current item and cleanup have completed.
- Partial results explicitly report succeeded, skipped, failed, and not-processed targets. Only completed Copy/Move targets are included in Undo; Details may offer that Undo as a single recovery action when the entry is still valid. Retry remains restricted to the existing safe allowlist and is never offered for partial results with applied changes, overwrite, or skip outcomes.
- Compress writes to a same-directory temporary archive and atomically publishes it on success. Extract and Replace write temporary files and atomically replace their destinations, cleaning temporary files on cancellation or failure.

---

## Shell Command Execution

- Press `!` to execute a one-line shell command.
- Commands run in the background as a separate process, preventing unintended termination of zivo. They are not suitable for prompts, TUI apps, or other interactive input; use `t` for a foreground shell instead.
- The dialog identifies the working directory and keeps the exit code, stdout, and stderr available after completion. Press `r` to rerun the command or `t` to open its directory in an external terminal.
- Non-interactive commands receive no terminal input. stdout and stderr are retained independently up to 1 MiB by default, preserving the beginning and end; the default timeout is five minutes. Both limits are advanced `[background_commands]` settings.
- Press `Esc` to stop a running non-interactive command. Timeout and cancellation return to browsing, and Shell Command retains a `Result` action for captured output. Stopping a command cannot roll back side effects it already performed.
- TUI programs, prompts, and password input must use the foreground shell or a custom action in `terminal`/`terminal_window` mode; those interactive modes are not subject to these limits.

---

## Data Loss Prevention

- Invalid `config.toml` values never prevent zivo from starting. Unsupported values fall back to built-in defaults, and a warning is shown after the initial directory load.
- When `logging.enabled` is set to `true`, startup failures and unhandled exceptions are written to the log file for later investigation.
- zivo is designed with reversibility in mind for file operations, minimizing the impact of accidental actions.
