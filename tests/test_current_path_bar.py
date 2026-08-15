"""Tests for the CurrentPathBar widget."""

from __future__ import annotations

import asyncio

import pytest
from rich.style import Style
from rich.text import Text

from zivo.models import PathBarState
from zivo.ui.current_path_bar import CurrentPathBar
from zivo.windows_paths import (
    WINDOWS_DRIVES_LABEL,
    WINDOWS_DRIVES_ROOT,
)

# ---------------------------------------------------------------------------
# _render_path unit tests
# ---------------------------------------------------------------------------


def _meta_for_text(text: Text, substring: str) -> dict | None:
    """Return the meta dict attached to the first span covering *substring*."""
    for span in text.spans:
        snippet = text.plain[span.start : span.end]
        if substring in snippet and span.style is not None:
            meta = span.style.meta
            if meta:
                return meta
    return None


def test_render_path_posix_plain_text() -> None:
    text = CurrentPathBar._render_path("/home/user/dir")
    assert text.plain == "Current Path: /home/user/dir"


def test_render_path_posix_meta_on_segments() -> None:
    text = CurrentPathBar._render_path("/home/user/dir")

    root_meta = _meta_for_text(text, "/")
    assert root_meta is not None
    assert root_meta["path_segment"] == "/"
    assert root_meta["segment_index"] == 0

    home_meta = _meta_for_text(text, "home")
    assert home_meta is not None
    assert home_meta["path_segment"] == "/home"
    assert home_meta["segment_index"] == 1

    dir_meta = _meta_for_text(text, "dir")
    assert dir_meta is not None
    assert dir_meta["path_segment"] == "/home/user/dir"
    assert dir_meta["segment_index"] == 3


def test_render_path_posix_root_only() -> None:
    text = CurrentPathBar._render_path("/")
    assert text.plain == "Current Path: /"

    root_meta = _meta_for_text(text, "/")
    assert root_meta is not None
    assert root_meta["path_segment"] == "/"


def test_render_path_posix_separator_slashes_no_meta() -> None:
    text = CurrentPathBar._render_path("/a/b/c")
    # Text: "Current Path: /a/b/c"
    # "/" at index 0 is the root segment (has meta).
    # "/" before "b" and "/" before "c" are inter-segment separators and
    # should NOT have meta.
    prefix_len = len("Current Path: ")
    # Find all "/" positions after the prefix
    slash_positions = []
    pos = prefix_len
    while True:
        pos = text.plain.find("/", pos)
        if pos < 0:
            break
        slash_positions.append(pos)
        pos += 1
    # First "/" after prefix is the root segment (position 14).
    # Remaining "/" are inter-segment separators.
    inter_separators = slash_positions[1:]

    for span in text.spans:
        if span.style and span.style.meta:
            for sep_pos in inter_separators:
                if span.start <= sep_pos < span.end:
                    snippet = text.plain[span.start : span.end]
                    pytest.fail(
                        f"separator at position {sep_pos} ({snippet!r}) has meta",
                    )


def test_render_path_windows_plain_text() -> None:
    text = CurrentPathBar._render_path("C:\\Users\\foo")
    assert text.plain == "Current Path: C:\\Users\\foo"


def test_render_path_windows_meta_on_segments() -> None:
    text = CurrentPathBar._render_path("C:\\Users\\foo")

    root_meta = _meta_for_text(text, "C:")
    assert root_meta is not None, "drive-letter segment should have meta"
    assert isinstance(root_meta["path_segment"], str)

    users_meta = _meta_for_text(text, "Users")
    assert users_meta is not None, "Users segment should have meta"
    assert isinstance(users_meta["path_segment"], str)

    foo_meta = _meta_for_text(text, "foo")
    assert foo_meta is not None, "foo segment should have meta"
    assert "foo" in foo_meta["path_segment"]


def test_render_path_drives_root() -> None:
    text = CurrentPathBar._render_path(WINDOWS_DRIVES_ROOT)
    assert text.plain == f"Current Path: {WINDOWS_DRIVES_LABEL}"
    assert len(text.spans) == 0


def test_render_path_hovered_segment_has_underline() -> None:
    text = CurrentPathBar._render_path("/home/user", hovered_index=2)
    for span in text.spans:
        snippet = text.plain[span.start : span.end]
        if snippet == "user" and span.style is not None:
            assert span.style.underline is True
            assert span.style.bold is True
            return
    pytest.fail("hovered segment 'user' not found with underline style")


def test_render_path_non_hovered_segment_no_underline() -> None:
    text = CurrentPathBar._render_path("/home/user", hovered_index=0)
    for span in text.spans:
        snippet = text.plain[span.start : span.end]
        if snippet == "user" and span.style is not None:
            assert span.style.underline in (None, False)
            return
    pytest.fail("non-hovered segment 'user' not found")


def test_render_path_with_hovered_drives_root() -> None:
    text = CurrentPathBar._render_path(
        WINDOWS_DRIVES_ROOT, hovered_index=0,
    )
    assert text.plain == f"Current Path: {WINDOWS_DRIVES_LABEL}"


def test_set_path_updates_text_and_resets_hover() -> None:
    bar = CurrentPathBar("/old/path")
    assert bar.path == "/old/path"
    assert str(bar.renderable) == "Current Path: /old/path"
    bar._hovered_index = 1
    bar.set_path("/new/path")
    assert bar.path == "/new/path"
    assert bar._hovered_index is None
    assert str(bar.renderable) == "Current Path: /new/path"


def test_set_path_same_path_is_noop() -> None:
    bar = CurrentPathBar("/same")
    bar._hovered_index = 2
    bar.set_path("/same")
    assert bar._hovered_index == 2


def test_display_path_matches_plain_text() -> None:
    path = "/tmp/zivo-test"
    bar = CurrentPathBar(path)
    assert str(bar.renderable) == f"Current Path: {path}"


def test_render_path_state_exposes_history_controls_and_breadcrumb_metadata() -> None:
    rendered = CurrentPathBar._render_path_state(
        PathBarState(
            path="/home/user/project",
            can_go_back=True,
            can_go_forward=False,
        )
    )

    assert rendered.plain.startswith("[‹] [›]  Current Path: / › home › user › project")
    metadata = [span.style.meta for span in rendered.spans if span.style and span.style.meta]
    assert {"path_navigation": "back", "navigation_enabled": True} in metadata
    assert {"path_navigation": "forward", "navigation_enabled": False} in metadata
    assert {"path_segment": "/home/user", "segment_index": 2} in metadata


def test_render_path_state_elides_middle_segments_and_labels_search_workspace() -> None:
    rendered = CurrentPathBar._render_path_state(
        PathBarState(path="/home/user/projects/zivo/tests", show_history_controls=False),
        max_width=38,
    )
    assert "…" in rendered.plain
    assert "tests" in rendered.plain

    search = CurrentPathBar._render_path_state(
        PathBarState(
            path="search://filename%3Apy?target=all&hidden=false",
            show_history_controls=False,
        )
    )
    assert search.plain == "Search Workspace: search:filename:py"
    assert not any(
        span.style and span.style.meta and "path_segment" in span.style.meta
        for span in search.spans
    )


# ---------------------------------------------------------------------------
# Widget-level click / hover behaviour
# ---------------------------------------------------------------------------


def test_click_on_segment_posts_message() -> None:
    bar = CurrentPathBar("/home/user/dir")

    messages: list[CurrentPathBar.PathSegmentClicked] = []

    def _capture(msg: CurrentPathBar.PathSegmentClicked) -> None:
        messages.append(msg)

    # Monkey-patch post_message
    original = bar.post_message
    bar.post_message = _capture  # type: ignore[method-assign]
    try:
        bar.on_click(_make_click_event(
            meta={"path_segment": "/home/user", "segment_index": 2},
        ))
    finally:
        bar.post_message = original

    assert len(messages) == 1
    assert messages[0].path == "/home/user"


def test_click_on_prefix_does_nothing() -> None:
    bar = CurrentPathBar("/home/user/dir")

    messages: list[CurrentPathBar.PathSegmentClicked] = []
    original = bar.post_message
    bar.post_message = lambda msg: messages.append(msg)  # type: ignore[method-assign]
    try:
        bar.on_click(_make_click_event(meta={}))
    finally:
        bar.post_message = original

    assert len(messages) == 0


def test_click_on_enabled_history_control_posts_navigation_message() -> None:
    bar = CurrentPathBar(
        "/home/user/dir",
        state=PathBarState(path="/home/user/dir", can_go_back=True),
    )
    messages: list[CurrentPathBar.PathNavigationClicked] = []
    original = bar.post_message
    bar.post_message = lambda msg: messages.append(msg)  # type: ignore[method-assign]
    try:
        bar.on_click(_make_click_event(
            meta={"path_navigation": "back", "navigation_enabled": True},
        ))
    finally:
        bar.post_message = original

    assert len(messages) == 1
    assert messages[0].direction == "back"


def _make_click_event(*, meta: dict) -> object:
    """Create a minimal Click-like object with a style attribute."""

    class _FakeClick:
        def __init__(self) -> None:
            self.style = Style(meta=meta)
            self._stopped = False

        def stop(self) -> None:
            self._stopped = True

    return _FakeClick()


# ---------------------------------------------------------------------------
# App-level integration: clicking a path segment navigates
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_app_current_path_bar_segment_click_navigates(tmp_path) -> None:
    from tests.support.app import (
        build_snapshot as _build_snapshot,
    )
    from tests.support.app import (
        wait_for_snapshot_loaded as _wait_for_snapshot_loaded,
    )
    from zivo import create_app
    from zivo.services import FakeBrowserSnapshotLoader
    from zivo.state import DirectoryEntryState

    docs = tmp_path / "docs"
    docs.mkdir()
    readme = tmp_path / "README.md"
    readme.write_text("hello\n")

    path = str(tmp_path)
    docs_path = str(docs)
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: _build_snapshot(
                path,
                (
                    DirectoryEntryState(docs_path, "docs", "dir"),
                    DirectoryEntryState(str(readme), "README.md", "file"),
                ),
                child_path=docs_path,
                child_entries=(),
            ),
            docs_path: _build_snapshot(
                docs_path,
                (DirectoryEntryState(f"{docs_path}/file.txt", "file.txt", "file"),),
            ),
        }
    )
    app = create_app(snapshot_loader=loader, initial_path=path)
    async with app.run_test(size=(120, 20)):
        from zivo.ui import CurrentPathBar

        await _wait_for_snapshot_loaded(app, path)

        await app.on_current_path_bar_path_segment_clicked(
            CurrentPathBar.PathSegmentClicked(path=docs_path),
        )
        await _wait_for_snapshot_loaded(app, docs_path)

        assert app.app_state.current_path == docs_path


@pytest.mark.asyncio
async def test_app_current_path_bar_segment_click_navigates_active_transfer_pane(
    tmp_path,
) -> None:
    from tests.support.app import (
        build_snapshot as _build_snapshot,
    )
    from tests.support.app import (
        wait_for_snapshot_loaded as _wait_for_snapshot_loaded,
    )
    from zivo import create_app
    from zivo.services import FakeBrowserSnapshotLoader
    from zivo.state import DirectoryEntryState
    from zivo.state.actions import ToggleTransferMode
    from zivo.ui import CurrentPathBar

    path = str(tmp_path)
    readme = tmp_path / "README.md"
    readme.write_text("hello\n")
    loader = FakeBrowserSnapshotLoader(
        snapshots={
            path: _build_snapshot(
                path,
                (DirectoryEntryState(str(readme), "README.md", "file"),),
                child_path=path,
                child_entries=(),
            ),
        }
    )
    app = create_app(snapshot_loader=loader, initial_path=path)
    async with app.run_test(size=(120, 20)):
        await _wait_for_snapshot_loaded(app, path)

        await app.dispatch_actions((ToggleTransferMode(),))
        assert app.app_state.layout_mode == "transfer"

        await app.on_current_path_bar_path_segment_clicked(
            CurrentPathBar.PathSegmentClicked(path=path),
        )

        deadline = asyncio.get_running_loop().time() + 1.0
        while True:
            active_pane = (
                app.app_state.transfer_left
                if app.app_state.active_transfer_pane == "left"
                else app.app_state.transfer_right
            )
            assert active_pane is not None
            if active_pane.pending_snapshot_request_id is None:
                break
            if asyncio.get_running_loop().time() >= deadline:
                raise AssertionError("transfer pane snapshot did not finish")
            await asyncio.sleep(0.01)
        assert active_pane.current_path == path
