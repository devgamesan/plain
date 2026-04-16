import pytest

from zivo.adapters import LocalFileOperationAdapter
from zivo.adapters import file_operations as file_operations_module


def test_local_file_operation_adapter_copies_file_contents(tmp_path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("plain\n", encoding="utf-8")
    destination = tmp_path / "target.txt"

    adapter = LocalFileOperationAdapter()

    adapter.copy_path(str(source), str(destination))

    assert destination.read_text(encoding="utf-8") == "plain\n"


def test_local_file_operation_adapter_copies_directory_recursively(tmp_path) -> None:
    source_dir = tmp_path / "docs"
    source_dir.mkdir()
    nested = source_dir / "guide.txt"
    nested.write_text("guide\n", encoding="utf-8")
    destination = tmp_path / "docs-copy"

    adapter = LocalFileOperationAdapter()

    adapter.copy_path(str(source_dir), str(destination))

    assert (destination / "guide.txt").read_text(encoding="utf-8") == "guide\n"


def test_local_file_operation_adapter_copies_symlink_without_following_target(tmp_path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    target = source_dir / "target.txt"
    target.write_text("secret\n", encoding="utf-8")
    link = source_dir / "link.txt"
    link.symlink_to(target)
    destination = tmp_path / "copied-link.txt"

    adapter = LocalFileOperationAdapter()

    adapter.copy_path(str(link), str(destination))

    assert destination.is_symlink()
    assert destination.resolve() == target.resolve()
    assert destination.read_text(encoding="utf-8") == "secret\n"


def test_local_file_operation_adapter_copies_nested_symlinks_without_following_target(
    tmp_path,
) -> None:
    source_dir = tmp_path / "docs"
    source_dir.mkdir()
    target = tmp_path / "target.txt"
    target.write_text("secret\n", encoding="utf-8")
    (source_dir / "link.txt").symlink_to(target)
    destination = tmp_path / "docs-copy"

    adapter = LocalFileOperationAdapter()

    adapter.copy_path(str(source_dir), str(destination))

    copied_link = destination / "link.txt"
    assert copied_link.is_symlink()
    assert copied_link.resolve() == target.resolve()


def test_local_file_operation_adapter_rejects_copy_to_same_path(tmp_path) -> None:
    source = tmp_path / "README.md"
    source.write_text("plain\n", encoding="utf-8")

    adapter = LocalFileOperationAdapter()

    with pytest.raises(OSError, match="Source and destination are the same path"):
        adapter.copy_path(str(source), str(source))


def test_local_file_operation_adapter_moves_paths(tmp_path) -> None:
    source = tmp_path / "notes.txt"
    source.write_text("move\n", encoding="utf-8")
    destination = tmp_path / "renamed.txt"

    adapter = LocalFileOperationAdapter()

    adapter.move_path(str(source), str(destination))

    assert source.exists() is False
    assert destination.read_text(encoding="utf-8") == "move\n"


def test_local_file_operation_adapter_rejects_move_to_same_path(tmp_path) -> None:
    source = tmp_path / "README.md"
    source.write_text("plain\n", encoding="utf-8")

    adapter = LocalFileOperationAdapter()

    with pytest.raises(OSError, match="Source and destination are the same path"):
        adapter.move_path(str(source), str(source))


def test_local_file_operation_adapter_moves_symlink_without_following_target(tmp_path) -> None:
    target = tmp_path / "target.txt"
    target.write_text("secret\n", encoding="utf-8")
    link = tmp_path / "link.txt"
    link.symlink_to(target)
    destination = tmp_path / "renamed-link.txt"

    adapter = LocalFileOperationAdapter()

    adapter.move_path(str(link), str(destination))

    assert link.exists() is False
    assert destination.is_symlink()
    assert target.exists()
    assert target.read_text(encoding="utf-8") == "secret\n"


def test_local_file_operation_adapter_creates_file_and_directory(tmp_path) -> None:
    file_path = tmp_path / "README.md"
    directory_path = tmp_path / "docs"

    adapter = LocalFileOperationAdapter()

    adapter.create_file(str(file_path))
    adapter.create_directory(str(directory_path))

    assert file_path.is_file()
    assert directory_path.is_dir()


def test_local_file_operation_adapter_create_file_raises_for_existing_path(tmp_path) -> None:
    file_path = tmp_path / "README.md"
    file_path.write_text("plain\n", encoding="utf-8")

    adapter = LocalFileOperationAdapter()

    with pytest.raises(OSError):
        adapter.create_file(str(file_path))


def test_local_file_operation_adapter_create_directory_raises_for_existing_path(tmp_path) -> None:
    directory_path = tmp_path / "docs"
    directory_path.mkdir()

    adapter = LocalFileOperationAdapter()

    with pytest.raises(OSError):
        adapter.create_directory(str(directory_path))


def test_local_file_operation_adapter_generates_unique_file_and_directory_names(tmp_path) -> None:
    file_path = tmp_path / "README.md"
    file_path.write_text("plain\n", encoding="utf-8")
    (tmp_path / "README copy.md").write_text("copy\n", encoding="utf-8")
    directory_path = tmp_path / "docs"
    directory_path.mkdir()

    adapter = LocalFileOperationAdapter()

    renamed_file = adapter.generate_renamed_path(str(file_path))
    renamed_directory = adapter.generate_renamed_path(str(directory_path))

    assert renamed_file == str(tmp_path / "README copy 2.md")
    assert renamed_directory == str(tmp_path / "docs copy")


def test_local_file_operation_adapter_path_exists_recognizes_broken_symlink(tmp_path) -> None:
    broken = tmp_path / "broken.txt"
    broken.symlink_to(tmp_path / "missing-target.txt")

    adapter = LocalFileOperationAdapter()

    assert adapter.path_exists(str(broken)) is True


def test_local_file_operation_adapter_send_to_trash_uses_send2trash(tmp_path, monkeypatch) -> None:
    trashed: list[str] = []
    target = tmp_path / "README.md"
    target.write_text("plain\n", encoding="utf-8")

    def fake_send2trash(path: str) -> None:
        trashed.append(path)

    monkeypatch.setattr(file_operations_module, "send2trash", fake_send2trash)
    adapter = LocalFileOperationAdapter()

    adapter.send_to_trash(str(target))

    assert trashed == [str(target.absolute())]


def test_local_file_operation_adapter_send_to_trash_keeps_symlink_identity(
    tmp_path, monkeypatch
) -> None:
    trashed: list[str] = []
    target = tmp_path / "target.txt"
    target.write_text("plain\n", encoding="utf-8")
    link = tmp_path / "link.txt"
    link.symlink_to(target)

    def fake_send2trash(path: str) -> None:
        trashed.append(path)

    monkeypatch.setattr(file_operations_module, "send2trash", fake_send2trash)
    adapter = LocalFileOperationAdapter()

    adapter.send_to_trash(str(link))

    assert trashed == [str(link.absolute())]


def test_local_file_operation_adapter_send_to_trash_converts_oserror(
    tmp_path, monkeypatch
) -> None:
    target = tmp_path / "README.md"
    target.write_text("plain\n", encoding="utf-8")

    def fake_send2trash(path: str) -> None:
        raise OSError("permission denied")

    monkeypatch.setattr(file_operations_module, "send2trash", fake_send2trash)
    adapter = LocalFileOperationAdapter()

    with pytest.raises(OSError, match="permission denied"):
        adapter.send_to_trash(str(target))


def test_local_file_operation_adapter_paths_are_same_returns_false_for_nonexistent_paths() -> None:
    adapter = LocalFileOperationAdapter()

    assert adapter.paths_are_same("/nonexistent/a", "/nonexistent/b") is False


def test_local_file_operation_adapter_paths_are_same_detects_same_file(tmp_path) -> None:
    file_path = tmp_path / "README.md"
    file_path.write_text("content\n", encoding="utf-8")

    adapter = LocalFileOperationAdapter()

    assert adapter.paths_are_same(str(file_path), str(file_path)) is True


def test_local_file_operation_adapter_paths_are_same_detects_different_files(tmp_path) -> None:
    file_a = tmp_path / "a.txt"
    file_b = tmp_path / "b.txt"
    file_a.write_text("a\n", encoding="utf-8")
    file_b.write_text("b\n", encoding="utf-8")

    adapter = LocalFileOperationAdapter()

    assert adapter.paths_are_same(str(file_a), str(file_b)) is False


def test_local_file_operation_adapter_copy_path_rejects_same_path_via_samefile(tmp_path) -> None:
    source = tmp_path / "README.md"
    source.write_text("plain\n", encoding="utf-8")

    adapter = LocalFileOperationAdapter()

    with pytest.raises(OSError, match="Source and destination are the same path"):
        adapter.copy_path(str(source), str(source))
