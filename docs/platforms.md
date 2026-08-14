# Platform-Specific Setup

OS support status and dependency installation instructions for zivo.

> Audience: new users setting up zivo and checking optional tools on their OS.

---

## Supported OS

| OS | Support Status | Notes |
| --- | --- | --- |
| Ubuntu | Supported | Primary verified environment at the moment. |
| Ubuntu (WSL) | Supported | WSL running Ubuntu is part of the verified environments. |
| macOS | Supported | Grant Full Disk Access to your terminal for trash operations. |
| Windows | Supported | Drive navigation, file operations, clipboard, shell commands, external terminal, undo, and most features. `zivo-cd` is not yet available on Windows. zivo runs on Windows as a Python application; a standalone native executable is not provided. |

---

## Features requiring additional installation

zivo itself can be installed and started with `uv`. The core browser, PDF text
preview, and Office text preview do not require additional commands. Install
the following only when you need the corresponding optional feature.

| Feature | Additional installation |
| --- | --- |
| Image preview | `chafa` (required for image preview; compatible terminals can render high-fidelity output) |
| PDF fallback extraction | Optional `pdftotext`; built-in PDF text preview works without it |
| Office preview | None |
| Grep search | `ripgrep` |

Missing optional tools or unsupported files keep zivo running and show compact metadata plus an available fallback action instead of a traceback. PDF fallback extraction is attempted only after a completed extraction failure and remains bounded.

### CI coverage

The CI matrix runs the full `pytest` suite on Ubuntu and macOS. Native Windows runs the supported regression scope covering file operations, clipboard, archive extraction/compression, file and grep search, text replacement, configuration, and Office preview extraction (`tests/test_adapters_file_operations.py`, `tests/test_services_clipboard_operations.py`, `tests/test_services_file_mutations.py`, `tests/test_services_archive_extract.py`, `tests/test_services_zip_compress.py`, `tests/test_services_file_search.py`, `tests/test_services_grep_search.py`, `tests/test_services_text_replace.py`, `tests/test_services_config.py`, and `tests/test_ooxml_preview.py`).

The full suite was evaluated for Issue #1160 and currently has 24 native-Windows failures caused by POSIX path/newline assumptions, chmod/chown semantics, and platform-specific UI timing. The Windows scope remains intentionally limited until those tests are ported. A test may be skipped on Windows only when its reason documents an OS-specific limitation, such as symlink privileges or permission semantics.

### OS-specific installation examples

```bash
# Ubuntu / Debian (X11)
sudo apt install chafa poppler-utils ripgrep xclip

# Ubuntu / Debian (Wayland)
sudo apt install chafa poppler-utils ripgrep wl-clipboard

# Ubuntu (WSL)
sudo apt install chafa poppler-utils ripgrep wslu

# macOS
brew install chafa poppler ripgrep
```

### OS details

#### Windows

On Windows, drive roots such as `C:\` support pressing `←` to return to the drive list so you can switch between drives without leaving zivo.

Install the required dependencies from their official websites:

- Office preview: built-in text extraction (no external command)
- Image preview: [chafa](https://hpjansson.org/chafa/) (the Kitty graphics protocol requires a terminal such as [Kitty](https://sw.kovidgoyal.net/kitty/), [Ghostty](https://ghostty.org/), or [WezTerm](https://wezfurlong.org/wezterm/))
- PDF preview fallback (`pdftotext`): [poppler for Windows](https://github.com/oschwartz10612/poppler-windows)
- Grep search: [ripgrep](https://github.com/BurntSushi/ripgrep)

#### macOS permissions

On macOS, grant **Full Disk Access** to your terminal application.

Open **System Settings > Privacy & Security > Full Disk Access** and enable the terminal app you use to run zivo (for example Terminal.app, iTerm2, or Alacritty). Without this permission, operations that access `~/.Trash` or other protected directories will fail.

---

## WSL Notes

- `wslu` is recommended on WSL so `wslview` is available for the preferred bridge behavior.
- On WSL, zivo prefers Windows-side bridges such as `wslview`, `explorer.exe`, and `clip.exe` when available, while keeping Linux-side fallbacks for WSLg and desktop Linux environments.

## Shell command syntax

Run command (`!`) uses the current shell environment on macOS, Linux, and WSL (falling back to `/bin/bash`). On Windows it prefers `powershell.exe`, then `pwsh`, then `cmd.exe`; write syntax for the selected shell rather than POSIX `sh`. Run command is for short non-interactive work. Use foreground shell (`t`) for prompts or TUI applications, and choose `Open current directory with terminal` from the command palette for independent or longer-running work.

---

## GUI Integration Notes

GUI integration (default-app launch, file-manager launch, external terminal launch) is currently verified mainly on Ubuntu and Ubuntu running under WSL.
