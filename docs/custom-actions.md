# Custom Actions

Custom actions let `config.toml` add command palette entries. They are intended for project-local tools such as formatters, checkers, optimizers, archive commands, and terminal apps.

## Configuration

Add `[[actions.custom]]` tables to `config.toml`.

```toml
[[actions.custom]]
name = "Optimize PNG"
command = ["oxipng", "-o", "4", "{file}"]
when = "single_file"
mode = "background"
extensions = ["png"]

[[actions.custom]]
name = "Create tar.gz from selection"
command = ["tar", "-czf", "{cwd_basename}.tar.gz", "{selection}"]
when = "selection"
mode = "background"

[[actions.custom]]
name = "Open lazygit"
command = ["lazygit"]
when = "always"
mode = "terminal"
cwd = "{cwd}"

[[actions.custom]]
name = "Open lazygit in new window"
command = ["lazygit"]
when = "always"
mode = "terminal_window"
cwd = "{cwd}"
```

## Fields

| Field | Required | Description |
| --- | --- | --- |
| `name` | yes | Label shown in the command palette. |
| `command` | yes | argv array to run. zivo does not run it through a shell. |
| `when` | no | `always`, `single_file`, or `selection`. Defaults to `always`. |
| `mode` | no | `background` or `terminal`. Defaults to `background`. |
| `cwd` | no | Working directory template. Defaults to `{cwd}`. |
| `extensions` | no | File extensions used with `single_file`, without or with leading dots. |

## Modes

`background` is for non-interactive commands. zivo captures stdout/stderr and shows a success or failure message in the status bar. Do not use this mode for TUI apps that need a terminal.

`terminal` is for TUI or interactive commands such as `lazygit`. zivo temporarily suspends its own interface, runs the command in the current terminal, then returns when the command exits.

`terminal_window` opens a new terminal window or tab to run the command. zivo does not suspend; the new window runs independently with a shell prompt after the command completes. This is useful for tools you want to run side-by-side with zivo.

## Variables

| Variable | Description |
| --- | --- |
| `{cwd}` | Current zivo directory. |
| `{cwd_basename}` | Basename of `{cwd}`. |
| `{file}` | Focused single file path. Requires `single_file`. |
| `{name}` | Focused file basename. |
| `{stem}` | Focused file name without extension. |
| `{ext}` | Focused file extension without the leading dot. |
| `{selection}` | Selected paths, expanded as multiple argv items. |

`{selection}` must be its own `command` array item. For example, `"{selection}"` is valid, but `"files={selection}"` is rejected.

## Safety

zivo shows the expanded command, working directory, and mode before running any custom action. Destructive command detection is not automatic, so keep destructive actions explicit in their names and prefer commands that already ask for confirmation.
