from zivo.path_validation import validate_path_segment


def test_validate_path_segment_rejects_null_and_macos_colon() -> None:
    assert validate_path_segment("bad\x00name") == "Names cannot include null characters"
    assert validate_path_segment("bad:name", is_macos=True) == "Names cannot include colons"


def test_validate_path_segment_applies_windows_rules(monkeypatch) -> None:
    monkeypatch.setattr("zivo.path_validation.os.name", "nt")

    assert validate_path_segment("bad<name") == "Invalid path segment 'bad<name'"
    assert validate_path_segment("CON") == "Reserved path segment 'CON'"


def test_validate_path_segment_rejects_overlong_utf8_name() -> None:
    assert validate_path_segment("あ" * 86) == (
        "Path segment exceeds maximum length of 255 bytes"
    )
