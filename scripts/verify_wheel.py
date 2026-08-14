"""Verify the license and dependency policy of a built wheel."""

from __future__ import annotations

import argparse
from pathlib import Path
from zipfile import ZipFile


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("wheel", type=Path)
    wheel_path = parser.parse_args().wheel

    with ZipFile(wheel_path) as archive:
        names = set(archive.namelist())
        metadata_name = next(name for name in names if name.endswith(".dist-info/METADATA"))
        metadata = archive.read(metadata_name).decode("utf-8")
        dist_info = metadata_name.split("/", 1)[0]

    allowed_prefixes = ("zivo/", f"{dist_info}/")
    unexpected_files = sorted(name for name in names if not name.startswith(allowed_prefixes))
    if unexpected_files:
        raise SystemExit(
            "unexpected files were bundled in the wheel: " + ", ".join(unexpected_files[:5])
        )

    for license_name in ("LICENSE", "NOTICE.txt"):
        expected_path = f"{dist_info}/licenses/{license_name}"
        if expected_path not in names:
            raise SystemExit(f"missing wheel license file: {expected_path}")
        if f"License-File: {license_name}" not in metadata:
            raise SystemExit(f"missing License-File metadata: {license_name}")

    for dependency in ("pypdf", "send2trash", "textual"):
        if f"Requires-Dist: {dependency}" not in metadata:
            raise SystemExit(f"missing dependency metadata: {dependency}")

    if "License-Expression: MIT" not in metadata:
        raise SystemExit("missing SPDX license expression metadata")


if __name__ == "__main__":
    main()
