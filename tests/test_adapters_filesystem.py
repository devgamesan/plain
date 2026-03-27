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
