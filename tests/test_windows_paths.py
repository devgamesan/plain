"""Tests for windows_paths module functions."""

import os
from datetime import datetime

import pytest

from zivo.state.models import FileSearchResultState
from zivo.windows_paths import display_path, file_search_result_to_directory_entry


def test_file_search_result_to_directory_entry_includes_size_and_modified_at(tmp_path):
    """ファイル検索結果から DirectoryEntryState への変換で size と modified_at が設定されること"""
    # テスト用ファイルを作成
    test_file = tmp_path / "test.txt"
    test_file.write_text("content", encoding="utf-8")

    # FileSearchResultState を作成
    result = FileSearchResultState(
        path=str(test_file),
        display_path="test.txt",
        entry_type="file",
    )

    # 変換を実行
    entry = file_search_result_to_directory_entry(result)

    # 検証
    assert entry.path == str(test_file)
    assert entry.name == "test.txt"
    assert entry.kind == "file"
    assert entry.size_bytes == len("content")
    assert entry.modified_at is not None
    assert isinstance(entry.modified_at, datetime)


def test_file_search_result_to_directory_entry_for_directory(tmp_path):
    """ディレクトリの場合、size_bytes が None であること"""
    test_dir = tmp_path / "docs"
    test_dir.mkdir()

    result = FileSearchResultState(
        path=str(test_dir),
        display_path="docs",
        entry_type="directory",
    )

    entry = file_search_result_to_directory_entry(result)

    assert entry.kind == "dir"
    assert entry.size_bytes is None
    assert entry.modified_at is not None
    assert isinstance(entry.modified_at, datetime)


def test_file_search_result_to_directory_entry_handles_hidden_files(tmp_path):
    """隠しファイルの hidden フラグが正しく設定されること"""
    hidden_file = tmp_path / ".hidden"
    hidden_file.write_text("secret", encoding="utf-8")

    result = FileSearchResultState(
        path=str(hidden_file),
        display_path=".hidden",
        entry_type="file",
    )

    entry = file_search_result_to_directory_entry(result)

    assert entry.hidden is True


def test_file_search_result_to_directory_entry_handles_missing_files(tmp_path):
    """ファイルが存在しない場合、基本情報のみの DirectoryEntryState が返されること"""
    missing_file = tmp_path / "missing.txt"

    result = FileSearchResultState(
        path=str(missing_file),
        display_path="missing.txt",
        entry_type="file",
    )

    entry = file_search_result_to_directory_entry(result)

    # 基本情報は利用可能
    assert entry.path == str(missing_file)
    assert entry.name == "missing.txt"
    assert entry.kind == "file"
    # メタデータは利用不可
    assert entry.size_bytes is None
    assert entry.modified_at is None


@pytest.mark.skipif(os.name == "nt", reason="symlink creation requires extra Windows privileges")
def test_file_search_result_to_directory_entry_marks_symlinks(tmp_path):
    """シンボリックリンクの symlink フラグが正しく設定されること"""
    target = tmp_path / "target.txt"
    target.write_text("content", encoding="utf-8")
    link = tmp_path / "link.txt"
    link.symlink_to(target)

    result = FileSearchResultState(
        path=str(link),
        display_path="link.txt",
        entry_type="file",
    )

    entry = file_search_result_to_directory_entry(result)

    assert entry.symlink is True


def test_file_search_result_to_directory_entry_raises_type_error_for_invalid_input():
    """FileSearchResultState 以外の型が渡された場合、TypeError が発生すること"""
    with pytest.raises(TypeError, match="Expected FileSearchResultState"):
        file_search_result_to_directory_entry("not a FileSearchResultState")


def test_file_search_result_to_directory_entry_for_empty_file(tmp_path):
    """空のファイルの場合、size_bytes が 0 であること"""
    empty_file = tmp_path / "empty.txt"
    empty_file.write_text("", encoding="utf-8")

    result = FileSearchResultState(
        path=str(empty_file),
        display_path="empty.txt",
        entry_type="file",
    )

    entry = file_search_result_to_directory_entry(result)

    assert entry.size_bytes == 0
    assert entry.modified_at is not None


def test_file_search_result_to_directory_entry_for_unicode_filename(tmp_path):
    """Unicode を含むファイル名で正しく動作すること"""
    unicode_file = tmp_path / "テストファイル.txt"
    unicode_file.write_text("content", encoding="utf-8")

    result = FileSearchResultState(
        path=str(unicode_file),
        display_path="テストファイル.txt",
        entry_type="file",
    )

    entry = file_search_result_to_directory_entry(result)

    assert entry.name == "テストファイル.txt"
    assert entry.size_bytes == len("content")
    assert entry.modified_at is not None


def test_display_path_for_search_workspace_with_query_and_root():
    """search workspace パスのクエリと root が正しくデコードされること"""
    path = "search://filename%3Apy?target=all&hidden=false&root=%2Fhome"
    result = display_path(path)
    assert result == "search:filename:py (root:/home)"


def test_display_path_for_search_workspace_without_root():
    """root がない search workspace パスが正しく表示されること"""
    path = "search://?target=all&hidden=false"
    result = display_path(path)
    assert result == "search:all"


def test_display_path_for_search_workspace_with_empty_query():
    """クエリが空の場合、'all' と表示されること"""
    path = "search://?target=all&hidden=false&root=%2Fhome"
    result = display_path(path)
    assert result == "search:all (root:/home)"


def test_display_path_for_regular_path():
    """通常のパスがそのまま返されること"""
    path = "/home/user/documents"
    result = display_path(path)
    assert result == path


def test_display_path_for_windows_drives_root():
    """Windows drives root が正しく表示されること"""
    from zivo.windows_paths import WINDOWS_DRIVES_LABEL

    path = "::zivo::windows-drives::"
    result = display_path(path)
    assert result == WINDOWS_DRIVES_LABEL
