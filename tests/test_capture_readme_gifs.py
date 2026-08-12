"""Regression checks for the deterministic README GIF capture inputs."""

from scripts.capture_readme_gifs import (
    BASE_PATH,
    DOCS_PATH,
    README_PATH,
    SRC_PATH,
    TARGET_SPECS,
    build_demo_loader,
)


def test_readme_capture_targets_match_documented_assets() -> None:
    assert TARGET_SPECS == {
        "basic_operation.gif": (1000, 640),
        "command_palette.gif": (1000, 462),
        "transfer_mode_operation.gif": (1000, 640),
    }


def test_demo_loader_has_fixed_snapshots_and_nonempty_child_previews() -> None:
    loader = build_demo_loader()

    snapshot = loader.snapshots[BASE_PATH]
    assert snapshot.current_pane.cursor_path == DOCS_PATH
    assert [entry.name for entry in snapshot.current_pane.entries] == [
        "docs",
        "src",
        "README.md",
    ]
    assert loader.child_panes[(BASE_PATH, DOCS_PATH)].entries
    assert loader.child_panes[(BASE_PATH, SRC_PATH)].entries
    readme_preview = loader.child_panes[(BASE_PATH, README_PATH)]
    assert readme_preview.mode == "preview"
    assert readme_preview.preview_title == "README.md"
    assert "three-pane browser" in (readme_preview.preview_content or "")
