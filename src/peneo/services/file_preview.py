"""File preview content loading service."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from rich.syntax import Syntax


class FilePreviewService(Protocol):
    """Boundary for loading file preview content outside the reducer."""

    def load_file_preview(
        self,
        path: str,
        max_size: int,
        max_lines: int,
    ) -> tuple[str, str | None, str | None]:
        """Load file preview content.

        Returns:
            A tuple of (highlighted_content, plain_content, error_message).
            If successful, error_message is None.
            If failed, highlighted_content and plain_content are None.
        """
        ...


@dataclass(frozen=True)
class LiveFilePreviewService:
    """Load file preview content from the local filesystem."""

    # Supported file extensions for syntax highlighting
    # Mapping from extension to lexer name (or None for auto-detection)
    SYNTAX_EXTENSIONS: dict[str, str | None] = field(default_factory=lambda: {
        # Code files
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".tsx": "tsx",
        ".jsx": "jsx",
        ".java": "java",
        ".c": "c",
        ".h": "c",
        ".cpp": "cpp",
        ".hpp": "cpp",
        ".cc": "cpp",
        ".cxx": "cpp",
        ".hxx": "cpp",
        ".cs": "csharp",
        ".go": "go",
        ".rs": "rust",
        ".php": "php",
        ".rb": "ruby",
        ".swift": "swift",
        ".kt": "kotlin",
        ".scala": "scala",
        ".m": "objective-c",
        ".mm": "objective-c++",
        ".sh": "bash",
        ".bash": "bash",
        ".zsh": "zsh",
        ".fish": "fish",
        ".ps1": "powershell",
        ".bat": "batch",
        ".cmd": "batch",
        ".pl": "perl",
        ".pm": "perl",
        ".r": "r",
        ".sql": "sql",
        ".lua": "lua",
        ".tcl": "tcl",
        ".ex": "elixir",
        ".exs": "elixir",
        ".erl": "erlang",
        ".hs": "haskell",
        ".lhs": "lhaskell",
        ".ml": "ocaml",
        ".mli": "ocaml",
        ".f90": "fortran",
        ".f95": "fortran",
        ".adb": "ada",
        ".ads": "ada",
        ".v": "verilog",
        ".sv": "systemverilog",
        ".vhdl": "vhdl",
        ".clj": "clojure",
        ".cljs": "clojure",
        ".groovy": "groovy",
        ".sc": "scala",
        ".dart": "dart",
        ".nim": "nim",
        ".pwn": "pawn",
        ".px": "pawn",
        ".p4": "pawn",
        # Markup and data
        ".md": "markdown",
        ".rst": "rst",
        ".html": "html",
        ".htm": "html",
        ".xml": "xml",
        ".xhtml": "xml",
        ".css": "css",
        ".scss": "scss",
        ".sass": "sass",
        ".less": "less",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".toml": "toml",
        ".ini": "ini",
        ".cfg": "ini",
        ".conf": "ini",
        ".properties": "properties",
        ".csv": "csv",
        ".tsv": "csv",
        # Build and config
        ".cmake": "cmake",
        "CMakeLists.txt": "cmake",
        "Makefile": "make",
        ".mk": "make",
        ".dockerfile": "dockerfile",
        "Dockerfile": "dockerfile",
        ".gradle": "groovy",
        ".maven": "xml",
        "pom.xml": "xml",
        "build.gradle": "groovy",
        # Web templates
        ".vue": "vue",
        ".svelte": "svelte",
        # Text files (no syntax highlighting)
        ".txt": None,
        ".log": None,
        ".readme": None,
        ".authors": None,
        ".changes": None,
        ".news": None,
        ".contributing": None,
    })

    def load_file_preview(
        self,
        path: str,
        max_size: int,
        max_lines: int,
    ) -> tuple[str, str | None, str | None]:
        """Load file preview content.

        Args:
            path: File path to preview
            max_size: Maximum file size in bytes
            max_lines: Maximum number of lines to read

        Returns:
            A tuple of (highlighted_content, plain_content, error_message).
            If successful, error_message is None and highlighted_content/plain_content are set.
            If failed, highlighted_content and plain_content are None and error_message is set.
        """
        try:
            file_path = Path(path).expanduser().resolve()

            # Check if file exists
            if not file_path.exists():
                return None, None, "File not found"

            # Check if it's a file (not a directory)
            if not file_path.is_file():
                return None, None, "Not a file"

            # Check file size
            file_size = file_path.stat().st_size
            if file_size > max_size:
                return None, None, f"File too large ({file_size} > {max_size} bytes)"

            # Read file content
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    lines = []
                    for i, line in enumerate(f):
                        if i >= max_lines:
                            break
                        lines.append(line.rstrip("\n\r"))
                    content = "\n".join(lines)
            except UnicodeDecodeError:
                # Try with latin-1 as fallback
                try:
                    with open(file_path, "r", encoding="latin-1") as f:
                        lines = []
                        for i, line in enumerate(f):
                            if i >= max_lines:
                                break
                            lines.append(line.rstrip("\n\r"))
                        content = "\n".join(lines)
                except Exception:
                    return None, None, "Binary file or unsupported encoding"

            # Detect lexer from file extension
            lexer = self._detect_lexer(file_path)

            # Create syntax highlighted content
            if lexer is not None:
                try:
                    syntax = Syntax(
                        content,
                        lexer,
                        line_numbers=False,
                        word_wrap=False,
                    )
                    highlighted = str(syntax)
                except Exception:
                    # Fallback to plain content if syntax highlighting fails
                    highlighted = content
            else:
                # No syntax highlighting for this file type
                highlighted = content

            return highlighted, content, None

        except PermissionError:
            return None, None, "Permission denied"
        except OSError as e:
            return None, None, str(e)
        except Exception as e:
            return None, None, f"Unexpected error: {e}"

    def _detect_lexer(self, file_path: Path) -> str | None:
        """Detect the appropriate lexer for the given file.

        Args:
            file_path: Path to the file

        Returns:
            Lexer name or None for plain text
        """
        # Check by filename first (for files like Makefile, Dockerfile)
        filename = file_path.name
        if filename in self.SYNTAX_EXTENSIONS:
            return self.SYNTAX_EXTENSIONS[filename]

        # Check by extension
        extension = file_path.suffix.lower()
        return self.SYNTAX_EXTENSIONS.get(extension)
