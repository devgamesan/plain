import builtins
import os

import pytest

from zivo.adapters import LocalFilesystemAdapter


def test_local_filesystem_adapter_lists_entries_with_lightweight_directory_metadata(
    tmp_path,
) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    readme = tmp_path / "README.md"
    readme.write_text("plain\n", encoding="utf-8")
    hidden = tmp_path / ".hidden"
    hidden.write_text("secret\n", encoding="utf-8")

    adapter = LocalFilesystemAdapter()

    entries = adapter.list_directory(str(tmp_path))

    assert [entry.name for entry in entries] == ["docs", ".hidden", "README.md"]

    docs_entry = entries[0]
    hidden_entry = entries[1]
    readme_entry = entries[2]

    assert docs_entry.kind == "dir"
    assert docs_entry.size_bytes is None
    assert docs_entry.modified_at is not None
    assert docs_entry.permissions_mode is not None
    assert docs_entry.owner is None
    assert docs_entry.group is None

    assert hidden_entry.hidden is True
    assert hidden_entry.kind == "file"
    assert hidden_entry.permissions_mode is not None

    assert readme_entry.kind == "file"
    assert readme_entry.size_bytes == readme.stat().st_size
    assert readme_entry.permissions_mode is not None


def test_local_filesystem_adapter_list_directory_skips_owner_group_resolution(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "README.md").write_text("plain\n", encoding="utf-8")
    adapter = LocalFilesystemAdapter()

    original_import = builtins.__import__

    def _unexpected_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name in {"grp", "pwd"}:
            raise AssertionError(f"{name} should not be imported while listing directories")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", _unexpected_import)

    entries = adapter.list_directory(str(tmp_path))

    assert [entry.name for entry in entries] == ["docs", "README.md"]


def test_local_filesystem_adapter_inspect_entry_loads_detailed_metadata(tmp_path) -> None:
    pwd = pytest.importorskip("pwd")
    grp = pytest.importorskip("grp")
    readme = tmp_path / "README.md"
    readme.write_text("plain\n", encoding="utf-8")
    adapter = LocalFilesystemAdapter()

    entry = adapter.inspect_entry(str(readme))

    assert entry is not None
    stat_result = readme.stat()
    assert entry.kind == "file"
    assert entry.size_bytes == stat_result.st_size
    assert entry.permissions_mode == stat_result.st_mode
    assert entry.modified_at is not None
    assert entry.owner == pwd.getpwuid(stat_result.st_uid).pw_name
    assert entry.group == grp.getgrgid(stat_result.st_gid).gr_name
    assert entry.symlink is False


def test_local_filesystem_adapter_inspect_entry_returns_none_owner_group_when_unavailable(
    tmp_path,
    monkeypatch,
) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("plain\n", encoding="utf-8")
    adapter = LocalFilesystemAdapter()

    original_import = builtins.__import__

    def _import_with_missing_posix_modules(name, globals=None, locals=None, fromlist=(), level=0):
        if name in {"grp", "pwd"}:
            raise ImportError(f"No module named {name}")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", _import_with_missing_posix_modules)

    entry = adapter.inspect_entry(str(readme))

    assert entry is not None
    assert entry.owner is None
    assert entry.group is None


@pytest.mark.skipif(os.name == "nt", reason="symlink creation requires extra Windows privileges")
def test_local_filesystem_adapter_inspect_entry_marks_symlink(tmp_path) -> None:
    target = tmp_path / "README.md"
    target.write_text("plain\n", encoding="utf-8")
    link = tmp_path / "README.link"
    link.symlink_to(target)
    adapter = LocalFilesystemAdapter()

    entry = adapter.inspect_entry(str(link))

    assert entry is not None
    assert entry.symlink is True
    assert entry.kind == "file"


@pytest.mark.skipif(os.name == "nt", reason="symlink creation requires extra Windows privileges")
def test_local_filesystem_adapter_includes_broken_symlink_entries(tmp_path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    broken = tmp_path / "broken-link"
    broken.symlink_to(tmp_path / "missing-target")

    adapter = LocalFilesystemAdapter()

    entries = adapter.list_directory(str(tmp_path))

    assert [entry.name for entry in entries] == ["docs", "broken-link"]
    assert entries[1].symlink is True


@pytest.mark.skipif(os.name == "nt", reason="symlink creation requires extra Windows privileges")
def test_local_filesystem_adapter_treats_directory_symlink_as_dir(tmp_path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    docs_link = tmp_path / "docs-link"
    docs_link.symlink_to(docs, target_is_directory=True)

    adapter = LocalFilesystemAdapter()

    entries = adapter.list_directory(str(tmp_path))

    assert [entry.name for entry in entries] == ["docs", "docs-link"]
    assert entries[0].kind == "dir"
    assert entries[1].kind == "dir"
    assert entries[1].size_bytes is None


def test_local_filesystem_adapter_calculates_recursive_directory_size(tmp_path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text("guide", encoding="utf-8")
    nested = docs / "nested"
    nested.mkdir()
    (nested / "deep.txt").write_text("deep-data", encoding="utf-8")

    adapter = LocalFilesystemAdapter()

    size = adapter.calculate_directory_size(str(docs))

    assert size == len("guide") + len("deep-data")


@pytest.mark.skipif(os.name == "nt", reason="symlink creation requires extra Windows privileges")
def test_local_filesystem_adapter_directory_size_ignores_symlinks(tmp_path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    target = tmp_path / "target.txt"
    target.write_text("linked-data", encoding="utf-8")
    (docs / "guide.md").write_text("guide", encoding="utf-8")
    (docs / "target-link").symlink_to(target)

    adapter = LocalFilesystemAdapter()

    size = adapter.calculate_directory_size(str(docs))

    assert size == len("guide")


@pytest.mark.skipif(os.name == "nt", reason="permission semantics differ on Windows")
def test_local_filesystem_adapter_directory_size_skips_permission_denied_descendants(
    tmp_path,
) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text("guide", encoding="utf-8")
    private = docs / "private"
    private.mkdir()
    (private / "secret.txt").write_text("secret", encoding="utf-8")

    adapter = LocalFilesystemAdapter()

    private.chmod(0)
    try:
        size = adapter.calculate_directory_size(str(docs))
    finally:
        private.chmod(0o755)

    assert size == len("guide")
