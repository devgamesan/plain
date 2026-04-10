from peneo.adapters import LocalFilesystemAdapter


def test_local_filesystem_adapter_lists_entries_with_metadata(tmp_path) -> None:
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

    assert hidden_entry.hidden is True
    assert hidden_entry.kind == "file"
    assert hidden_entry.permissions_mode is not None

    assert readme_entry.kind == "file"
    assert readme_entry.size_bytes == len("plain\n")
    assert readme_entry.permissions_mode is not None


def test_local_filesystem_adapter_skips_broken_symlink_entries(tmp_path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    broken = tmp_path / "broken-link"
    broken.symlink_to(tmp_path / "missing-target")

    adapter = LocalFilesystemAdapter()

    entries = adapter.list_directory(str(tmp_path))

    assert [entry.name for entry in entries] == ["docs"]


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
