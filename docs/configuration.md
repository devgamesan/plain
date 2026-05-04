# Configuration

On startup, zivo reads `config.toml` from the platform-specific user config directory.
If the file does not exist yet, zivo creates it automatically with default values.

`config.toml` location by OS:

- Linux: `${XDG_CONFIG_HOME:-~/.config}/zivo/config.toml`
- macOS: `~/Library/Application Support/zivo/config.toml`
- Windows: `%APPDATA%\\zivo\\config.toml`

## Settings Reference

| Section | Key | Values | Description |
| --- | --- | --- | --- |
| `terminal` | `linux` | Array of shell-style command templates | Optional terminal launch commands for Linux. Use `{path}` as the working-directory placeholder. Invalid or empty entries are ignored. |
| `terminal` | `macos` | Array of shell-style command templates | Optional terminal launch commands for macOS, validated the same way as Linux entries. |
| `terminal` | `windows` | Array of shell-style command templates | Optional terminal launch commands for Windows and WSL bridge workflows. |
| `editor` | `command` | Shell-style string, for example `nvim -u NONE` | Optional terminal editor command used by `e`. Do not include the file path; zivo appends it automatically. Unsupported GUI editors or invalid commands are ignored. |
| `gui_editor` | `command` | Shell-style command template | GUI editor command used when line/column information is available. Use `{path}`, `{line}`, and `{column}`. Defaults to `code --goto {path}:{line}:{column}`. The config editor can switch between presets for VS Code, VSCodium, Cursor, Sublime Text, Zed, JetBrains IDEA, PyCharm, WebStorm, and Kate. |
| `gui_editor` | `fallback_command` | Shell-style command template | GUI editor command used when opening a path without a match location, or when `command` fails. Use `{path}`. Defaults to `code {path}`. Custom raw templates are preserved and shown as custom in the config editor. |
| `display` | `show_hidden_files` | `true` / `false` | Default hidden-file visibility when the app starts. |
| `display` | `show_directory_sizes` | `true` / `false` | Shows recursive directory sizes in the current pane. Defaults to `true`. Large directories can be expensive to scan. zivo also calculates sizes automatically while the main pane is sorted by `size`. |
| `display` | `enable_text_preview` | `true` / `false` | Shows text-file previews in the right pane. Defaults to `true`. grep result context preview follows the same setting. |
| `display` | `enable_image_preview` | `true` / `false` | Shows image-file previews in the right pane through `chafa`. Defaults to `true`. When `chafa` is missing, zivo shows a dependency message instead of failing. Set `image_preview_mode` to `kitty` for high-fidelity image rendering on compatible terminals. |
| `display` | `image_preview_mode` | `auto` / `kitty` / `chafa` | Selects the image preview backend. Defaults to `auto`. `auto` detects terminal support — uses the Kitty graphics protocol on Kitty, Ghostty, or compatible terminals; falls back to chafa Unicode symbols otherwise. `kitty` forces Kitty graphics protocol (requires a compatible terminal). `chafa` forces the legacy Unicode symbol output. |
| `display` | `enable_pdf_preview` | `true` / `false` | Enables PDF preview conversion through `pdftotext`. Defaults to `true`. When disabled, PDF files fall back to the usual unsupported-file message. |
| `display` | `enable_office_preview` | `true` / `false` | Enables `pandoc`-based preview conversion for `docx`, `xlsx`, and `pptx` files. Defaults to `true`. When disabled, those formats fall back to the usual unsupported-file message. |
| `display` | `show_help_bar` | `true` / `false` | Shows the help bar at the bottom of the screen. Defaults to `true`. The help bar is always shown when the command palette is open, regardless of this setting. |
| `display` | `theme` | Any built-in Textual theme, for example `textual-dark`, `textual-light`, `dracula`, or `tokyo-night` | Default UI theme applied on startup. In the settings editor, theme changes are previewed immediately and are persisted when you save. |
| `display` | `preview_syntax_theme` | `auto` or a supported Pygments style, for example `one-dark`, `xcode`, `nord`, or `gruvbox-dark` | Syntax-highlighting colors used by the right-pane text preview. `auto` keeps the current light/dark-based default selection. In the settings editor, changes are previewed immediately when a text preview is visible. |
| `display` | `preview_max_kib` | `64` / `128` / `256` / `512` / `1024` | Maximum amount of text read for right-pane file previews and preview sampling. Defaults to `64`. Larger values allow deeper previews at the cost of more I/O. |
| `display` | `default_sort_field` | `name` / `modified` / `size` | Default sort field for the main pane. |
| `display` | `default_sort_descending` | `true` / `false` | Starts the main-pane sort in descending order when enabled. |
| `display` | `directories_first` | `true` / `false` | Keeps directories grouped before files in the main pane. |
| `behavior` | `confirm_delete` | `true` / `false` | Shows a confirmation dialog before moving items to trash. Permanent delete via `D` / `Shift+Delete` always asks for confirmation. |
| `behavior` | `paste_conflict_action` | `prompt` / `overwrite` / `skip` / `rename` | Chooses the default paste-conflict behavior. `prompt` keeps the conflict dialog enabled. |
| `logging` | `enabled` | `true` / `false` | Enables file output for startup failures and unhandled exceptions. |
| `logging` | `level` | `DEBUG` / `INFO` / `WARNING` / `ERROR` / `CRITICAL` | Log level for file output. Defaults to `ERROR`. Requires app restart to take effect. |
| `logging` | `path` | Path string | Optional log file path. Leave empty to use `zivo.log` next to `config.toml`. Default log file locations: Linux: `~/.config/zivo/zivo.log`, macOS: `~/Library/Application Support/zivo/zivo.log`. |
| `bookmarks` | `paths` | Array of absolute path strings | Bookmarked directories shown by `b` and `Show bookmarks` in the command palette. Duplicate paths are removed when the config is loaded. |
| `file_search` | `max_results` | Integer or empty | Maximum number of file search results. Leave empty for unlimited (default). Set to reduce memory usage on large repositories. |
| `actions` | `custom` | Array of action tables | Custom command palette actions. See [Custom Actions](custom-actions.md). |

## Example

```toml
[terminal]
launch_mode = "window"
linux = ["konsole --working-directory {path}", "gnome-terminal --working-directory={path}"]
macos = ["open -a Terminal {path}"]
windows = ["wt -d {path}"]

[editor]
command = "nvim -u NONE"

[gui_editor]
command = "code --goto {path}:{line}:{column}"
fallback_command = "code {path}"

[display]
show_hidden_files = false
show_directory_sizes = true
enable_text_preview = true
enable_image_preview = true
image_preview_mode = "auto"
enable_pdf_preview = true
enable_office_preview = true
show_help_bar = true
theme = "textual-dark"
preview_syntax_theme = "auto"
preview_max_kib = 64
default_sort_field = "name"
default_sort_descending = false
directories_first = true

[behavior]
confirm_delete = true
paste_conflict_action = "prompt"

[logging]
enabled = true
level = "ERROR"
path = ""

[bookmarks]
paths = ["/home/user/src", "/home/user/docs"]
```

## Notes

- Invalid config values do not stop startup. zivo falls back to built-in defaults and shows a warning after the initial directory load.
- When logging is enabled, startup failures and unhandled exceptions are appended to the configured log file for later investigation.
- The accepted `display.theme` values come from the built-in themes shipped with the installed Textual version.
- The accepted `display.preview_syntax_theme` values are `auto` plus the Pygments styles available in the installed environment.
