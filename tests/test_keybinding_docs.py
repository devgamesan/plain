from pathlib import Path

REMOVED_DIRECT_KEYS = ("i", "C", "B", "M", "O", "T", "H", "R")


def test_keybinding_docs_do_not_advertise_removed_direct_keys() -> None:
    repository_root = Path(__file__).resolve().parents[1]

    for relative_path in ("docs/keybindings.md", "docs/keybindings.ja.md"):
        content = (repository_root / relative_path).read_text(encoding="utf-8")
        for key in REMOVED_DIRECT_KEYS:
            assert f"| `{key}` |" not in content


def test_keybinding_docs_describe_risky_permanent_delete_confirmation() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    english = (repository_root / "docs/keybindings.md").read_text(encoding="utf-8")
    japanese = (repository_root / "docs/keybindings.ja.md").read_text(encoding="utf-8")

    assert "`Enter` then `D`" in english
    assert "`Enter` → `D`" in japanese
