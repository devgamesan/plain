"""Regression checks for the public documentation topology and config reference."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_MARKDOWN = (ROOT / "README.md", ROOT / "README.ja.md", *sorted((ROOT / "docs").glob("*.md")))

LANGUAGE_PAIRS = (
    "architecture",
    "commands",
    "configuration",
    "custom-actions",
    "dependency-audit",
    "keybindings",
    "pdf-preview-decision",
    "performance",
    "platforms",
    "safety",
)

CONFIG_KEYS = (
    "linux",
    "macos",
    "windows",
    "command",
    "fallback_command",
    "show_hidden_files",
    "show_directory_sizes",
    "enable_text_preview",
    "enable_image_preview",
    "image_preview_mode",
    "enable_pdf_preview",
    "enable_office_preview",
    "show_help_bar",
    "theme",
    "preview_syntax_theme",
    "preview_max_kib",
    "default_sort_field",
    "default_sort_descending",
    "directories_first",
    "grep_preview_context_lines",
    "preview_word_wrap",
    "timeout_seconds",
    "stdout_max_kib",
    "stderr_max_kib",
    "image_timeout_seconds",
    "image_stdout_max_mib",
    "kitty_stdout_max_mib",
    "input_max_mib",
    "max_archive_entries",
    "max_archive_entry_mib",
    "max_archive_total_mib",
    "max_archive_compression_ratio",
    "timeout_cache_seconds",
    "confirm_delete",
    "confirm_exit",
    "paste_conflict_action",
    "enabled",
    "path",
    "level",
    "paths",
    "max_results",
    "max_output_kib",
    "custom",
)

MARKDOWN_LINK_RE = re.compile(
    r"(?P<image>!)?\[[^\]]*\]\((?P<target>[^)]+)\)"
)


def test_public_markdown_links_and_images_resolve() -> None:
    """Keep README/docs navigation and image assets valid after file moves."""

    for document in PUBLIC_MARKDOWN:
        text = document.read_text(encoding="utf-8")
        for match in MARKDOWN_LINK_RE.finditer(text):
            target = match.group("target").split("#", 1)[0].strip()
            if not target or target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            target_path = (document.parent / target).resolve()
            assert target_path.exists(), f"broken link in {document.relative_to(ROOT)}: {target}"
            if match.group("image"):
                alt_text = match.group(0).split("](", 1)[0][2:]
                assert alt_text.strip(), (
                    f"image is missing alt text in {document.relative_to(ROOT)}"
                )


def test_public_documents_use_one_language_naming_convention() -> None:
    """English is the canonical filename and Japanese uses the .ja suffix."""

    docs_dir = ROOT / "docs"
    for stem in LANGUAGE_PAIRS:
        assert (docs_dir / f"{stem}.md").is_file()
        assert (docs_dir / f"{stem}.ja.md").is_file()
    assert not list(docs_dir.glob("*.en.md"))


def test_configuration_reference_covers_normalized_config_keys() -> None:
    """Keep both configuration tables aligned with the loader/rendered config."""

    for name in ("configuration.md", "configuration.ja.md"):
        text = (ROOT / "docs" / name).read_text(encoding="utf-8")
        for key in CONFIG_KEYS:
            assert f"`{key}`" in text, f"{key} is missing from {name}"
        assert "launch_mode =" not in text
