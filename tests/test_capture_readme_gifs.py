"""Regression checks for the deterministic README GIF capture inputs."""

from scripts.capture_readme_gifs import (
    BASE_PATH,
    DOCS_PATH,
    README_PATH,
    SRC_PATH,
    TARGET_SPECS,
    _apply_capture_colors,
    build_demo_loader,
)


def test_readme_capture_targets_match_documented_assets() -> None:
    assert TARGET_SPECS == {
        "basic_operation.gif": (1920, 1080),
        "command_palette.gif": (1920, 1080),
        "transfer_mode_operation.gif": (1920, 1080),
    }


def test_demo_loader_has_fixed_snapshots_and_nonempty_child_previews() -> None:
    loader = build_demo_loader()

    snapshot = loader.snapshots[BASE_PATH]
    assert snapshot.current_pane.cursor_path == DOCS_PATH
    assert [entry.name for entry in snapshot.current_pane.entries[:3]] == [
        "docs", "src", "tests"
    ]
    assert len(snapshot.current_pane.entries) == 8
    assert snapshot.parent_pane.directory_path == "/Users/demo/Projects"
    assert snapshot.parent_pane.entries[0].name == "zivo"
    assert loader.child_panes[(BASE_PATH, DOCS_PATH)].entries
    assert loader.child_panes[(BASE_PATH, SRC_PATH)].entries
    readme_preview = loader.child_panes[(BASE_PATH, README_PATH)]
    assert readme_preview.mode == "preview"
    assert readme_preview.preview_title == "README.md"
    assert "keyboard-first file browser" in (readme_preview.preview_content or "")


def test_capture_colors_restore_theme_palette(tmp_path) -> None:
    svg_path = tmp_path / "frame.svg"
    svg_path.write_text(
        '<style>.terminal-demo-r7 { fill: #b0b0b0 }</style>'
        '<rect fill="#222222" />',
        encoding="utf-8",
    )

    _apply_capture_colors(svg_path)

    rendered = svg_path.read_text(encoding="utf-8")
    assert "#fab387" in rendered
    assert "#1e1e2e" in rendered
