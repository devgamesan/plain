"""Test Services Browser Snapshot Text tests."""

from tests.support.browser_snapshot import (
    PREVIEW_PERMISSION_DENIED_MESSAGE,
    LiveBrowserSnapshotLoader,
    StubFilesystemAdapter,
    pytest,
)


def test_live_browser_snapshot_loader_previews_text_file_without_extension(tmp_path) -> None:
    """拡張子がないテキストファイルをプレビューできること."""
    project = tmp_path / "project"
    project.mkdir()
    readme = project / "README"
    readme.write_text("This is a README file.\n", encoding="utf-8")

    loader = LiveBrowserSnapshotLoader()

    snapshot = loader.load_browser_snapshot(str(project), cursor_path=str(readme))

    assert snapshot.current_pane.cursor_path == str(readme)
    assert snapshot.child_pane.mode == "preview"
    assert snapshot.child_pane.preview_path == str(readme)
    assert snapshot.child_pane.preview_content == "This is a README file.\n"
    assert snapshot.child_pane.preview_truncated is False

def test_live_browser_snapshot_loader_previews_text_file_with_unknown_extension(tmp_path) -> None:
    """拡張子リストにないテキストファイルをプレビューできること."""
    project = tmp_path / "project"
    project.mkdir()
    custom = project / "config.custom"
    custom.write_text("custom setting\n", encoding="utf-8")

    loader = LiveBrowserSnapshotLoader()

    snapshot = loader.load_browser_snapshot(str(project), cursor_path=str(custom))

    assert snapshot.current_pane.cursor_path == str(custom)
    assert snapshot.child_pane.mode == "preview"
    assert snapshot.child_pane.preview_path == str(custom)
    assert snapshot.child_pane.preview_content == "custom setting\n"
    assert snapshot.child_pane.preview_truncated is False

def test_live_browser_snapshot_loader_rejects_binary_file_with_unknown_extension(tmp_path) -> None:
    """拡張子リストにないバイナリファイルをプレビューしないこと."""
    project = tmp_path / "project"
    project.mkdir()
    binary = project / "data.unknown"
    binary.write_bytes(b"\x00\x01\x02\x03\x04\x05")

    loader = LiveBrowserSnapshotLoader()

    snapshot = loader.load_browser_snapshot(str(project), cursor_path=str(binary))

    assert snapshot.current_pane.cursor_path == str(binary)
    assert snapshot.child_pane.mode == "preview"
    assert snapshot.child_pane.preview_path == str(binary)
    assert snapshot.child_pane.preview_content is None
    assert snapshot.child_pane.preview_message == "Preview unavailable for this file type"

def test_live_browser_snapshot_loader_previews_empty_file_as_text(tmp_path) -> None:
    """空ファイルをテキストとしてプレビューできること."""
    project = tmp_path / "project"
    project.mkdir()
    empty = project / "empty.txt"
    empty.write_text("", encoding="utf-8")

    loader = LiveBrowserSnapshotLoader()

    snapshot = loader.load_browser_snapshot(str(project), cursor_path=str(empty))

    assert snapshot.current_pane.cursor_path == str(empty)
    assert snapshot.child_pane.mode == "preview"
    assert snapshot.child_pane.preview_path == str(empty)
    assert snapshot.child_pane.preview_content == ""
    assert snapshot.child_pane.preview_truncated is False

def test_live_browser_snapshot_loader_previews_high_printable_ratio_file(tmp_path) -> None:
    """printable率が70%以上のファイルをテキストとしてプレビューできること."""
    project = tmp_path / "project"
    project.mkdir()
    # printable率が高いテキスト（ASCII文字のみ）
    text = project / "high_printable.txt"
    text.write_text("Hello World! " * 50 + "\n", encoding="utf-8")

    loader = LiveBrowserSnapshotLoader()

    snapshot = loader.load_browser_snapshot(str(project), cursor_path=str(text))

    assert snapshot.current_pane.cursor_path == str(text)
    assert snapshot.child_pane.mode == "preview"
    assert snapshot.child_pane.preview_path == str(text)
    assert snapshot.child_pane.preview_content is not None
    assert "Hello World!" in snapshot.child_pane.preview_content

def test_live_browser_snapshot_loader_rejects_low_printable_ratio_file(tmp_path) -> None:
    """printable率が70%未満のファイルをバイナリとして扱うこと."""
    project = tmp_path / "project"
    project.mkdir()
    # printable率が低いデータ（バイナリっぽいデータ）
    binary = project / "low_printable.dat"
    # 70%未満のprintable率になるように作成
    content = bytes([i % 256 for i in range(512)])  # ランダムっぽいデータ
    binary.write_bytes(content)

    loader = LiveBrowserSnapshotLoader()

    snapshot = loader.load_browser_snapshot(str(project), cursor_path=str(binary))

    assert snapshot.current_pane.cursor_path == str(binary)
    assert snapshot.child_pane.mode == "preview"
    assert snapshot.child_pane.preview_path == str(binary)
    assert snapshot.child_pane.preview_content is None
    assert snapshot.child_pane.preview_message == "Preview unavailable for this file type"

def test_live_browser_snapshot_loader_returns_permission_denied_for_denied_directory(
    tmp_path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    secret = project / "secret"
    secret.mkdir()

    loader = LiveBrowserSnapshotLoader(
        filesystem=StubFilesystemAdapter(
            entries_by_path={str(project): ()},
            errors_by_path={str(secret): PermissionError("blocked")},
        )
    )

    pane = loader.load_child_pane_snapshot(str(project), str(secret))

    assert pane.mode == "preview"
    assert pane.preview_message == PREVIEW_PERMISSION_DENIED_MESSAGE
    assert pane.entries == ()
    assert pane.directory_path == str(secret)

def test_live_browser_snapshot_loader_propagates_non_permission_os_error_for_directory(
    tmp_path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    inaccessible = project / "inaccessible"
    inaccessible.mkdir()

    loader = LiveBrowserSnapshotLoader(
        filesystem=StubFilesystemAdapter(
            entries_by_path={str(project): ()},
            errors_by_path={str(inaccessible): FileNotFoundError("gone")},
        )
    )

    with pytest.raises(OSError, match="Not found:"):
        loader.load_child_pane_snapshot(str(project), str(inaccessible))
