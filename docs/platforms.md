# Platform-Specific Setup

OS support status and dependency installation instructions for zivo.

---

## Supported OS

| OS | Support Status | Notes |
| --- | --- | --- |
| Ubuntu | Supported | Primary verified environment at the moment. |
| Ubuntu (WSL) | Supported | WSL running Ubuntu is part of the verified environments. |
| macOS | Supported | Grant Full Disk Access to your terminal for trash operations. |
| Windows | Supported | Drive navigation, file operations, clipboard, shell commands, external terminal, undo, and most features. `zivo-cd` is not yet available on Windows. |

---

## Recommended Tools

zivo itself can be installed and started with `uv`, but some features depend on external commands being available on `PATH`.

| Feature | Tool |
| --- | --- |
| Image preview | `chafa` |
| PDF preview | `pdftotext` / `poppler` |
| Office preview | `pandoc` |
| Grep search | `ripgrep` |

### OS-specific installation examples

```bash
# Ubuntu / Debian (X11)
sudo apt install chafa pandoc poppler-utils ripgrep xclip

# Ubuntu / Debian (Wayland)
sudo apt install chafa pandoc poppler-utils ripgrep wl-clipboard

# Ubuntu (WSL)
sudo apt install chafa pandoc poppler-utils ripgrep wslu

# macOS
brew install chafa pandoc poppler ripgrep
```

**Note**: Some distributions may not provide pandoc 3.8.3+ through their package managers. If the installed version is older than 3.8.3, install the latest version manually from the [official pandoc website](https://pandoc.org/installing.html).

### OS details

#### Windows

On Windows, drive roots such as `C:\` support pressing `←` to return to the drive list so you can switch between drives without leaving zivo.

Install the required dependencies from their official websites:

- Document preview: [pandoc](https://pandoc.org/)
- Image preview: [chafa](https://hpjansson.org/chafa/)
- PDF preview (`pdftotext`): [poppler for Windows](https://github.com/oschwartz10612/poppler-windows)
- Grep search: [ripgrep](https://github.com/BurntSushi/ripgrep)

#### macOS permissions

On macOS, grant **Full Disk Access** to your terminal application.

Open **System Settings > Privacy & Security > Full Disk Access** and enable the terminal app you use to run zivo (for example Terminal.app, iTerm2, or Alacritty). Without this permission, operations that access `~/.Trash` or other protected directories will fail.

---

## WSL Notes

- `wslu` is recommended on WSL so `wslview` is available for the preferred bridge behavior.
- On WSL, zivo prefers Windows-side bridges such as `wslview`, `explorer.exe`, and `clip.exe` when available, while keeping Linux-side fallbacks for WSLg and desktop Linux environments.

---

## GUI Integration Notes

GUI integration (default-app launch, file-manager launch, external terminal launch) is currently verified mainly on Ubuntu and Ubuntu running under WSL.
