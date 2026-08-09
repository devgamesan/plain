# Safety

zivo includes several safety mechanisms to prevent accidents during file operations.

---

## Move to Trash

- Press `d` or `Delete` to move selected items to the trash.
- A confirmation dialog is shown by default (configurable via `behavior.confirm_delete` in `config.toml`).
- On macOS and Linux, items are moved to the OS standard trash via `send2trash`.
- On Windows, items are moved to the Recycle Bin via `send2trash`.

---

## Permanent Delete

- Press `D` or `Shift+Delete` to permanently delete selected items.
- Permanent delete always asks for confirmation regardless of the `behavior.confirm_delete` setting.
- The confirmation shows the target count, total size, up to three representative names, and whether any sizes could not be read.
- Multiple targets or any directory require two explicit steps: press `Enter` to review, then uppercase `D` to delete.
- Unlike trash, these operations cannot be undone.

---

## Undo

- Press `z` to undo the most recent file operation.
- Undoable operations: rename, paste (including cross-pane Copy/Move in Transfer mode), and move to trash.
- `Undo last file operation` is hidden from the command palette when the undo history is empty.
- Only reversible file operations are recorded in the undo history.

## Bulk Rename

- Selecting two or more items and invoking `r` or `Rename selected items` opens a review overlay with Old Name / New Name / Status rows and a count summary before any filesystem change.
- Unchanged rows are skipped, and Find/Replace is literal (not regex). Any collision, invalid name, missing target, or parent-directory permission failure disables the apply action.
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
- Press `Enter` to confirm the replacement after reviewing changes.
- Use `Shift+↑` / `Shift+↓` to scroll the diff preview.

---

## Archive Extraction Safety

- If the destination already exists, a confirmation dialog is shown before extraction.
- The status bar shows entry-count progress while the extraction runs.

---

## Shell Command Execution

- Press `!` to execute a one-line shell command.
- Commands run in the background as a separate process, preventing unintended termination of zivo. They are not suitable for prompts, TUI apps, or other interactive input; use `t` for a foreground shell instead.
- The dialog identifies the working directory and keeps the exit code, stdout, and stderr available after completion. Press `r` to rerun the command or `t` to open its directory in an external terminal.

---

## Data Loss Prevention

- Invalid `config.toml` values never prevent zivo from starting. Unsupported values fall back to built-in defaults, and a warning is shown after the initial directory load.
- When `logging.enabled` is set to `true`, startup failures and unhandled exceptions are written to the log file for later investigation.
- zivo is designed with reversibility in mind for file operations, minimizing the impact of accidental actions.
