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
- Unlike trash, these operations cannot be undone.

---

## Undo

- Press `z` to undo the most recent file operation.
- Undoable operations: rename, paste, and move to trash.
- `Undo last file operation` is hidden from the command palette when the undo history is empty.
- Only reversible file operations are recorded in the undo history.

---

## Paste Conflict Resolution

- When the paste destination already contains a file with the same name, a conflict dialog is shown.
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
- Commands run in the background as a separate process, preventing unintended termination of zivo.
- The first output line or a failure summary is shown in the status bar.

---

## Data Loss Prevention

- Invalid `config.toml` values never prevent zivo from starting. Unsupported values fall back to built-in defaults, and a warning is shown after the initial directory load.
- When `logging.enabled` is set to `true`, startup failures and unhandled exceptions are written to the log file for later investigation.
- zivo is designed with reversibility in mind for file operations, minimizing the impact of accidental actions.
