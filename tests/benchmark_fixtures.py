"""
ベンチマーク用大規模 Fixture 生成モジュール

再現可能な大規模テストデータセットを生成する関数を提供します。
"""

from pathlib import Path

from tests.state_test_helpers import entry


def create_large_directory(
    base_path: Path,
    num_dirs: int = 200,
    num_files: int = 800,
) -> Path:
    """
    大規模ディレクトリを作成（既存スモークテストと同様の構造）

    Args:
        base_path: ベースパス
        num_dirs: ディレクトリ数（デフォルト: 200）
        num_files: ファイル数（デフォルト: 800）

    Returns:
        作成されたディレクトリのパス
    """
    base_path.mkdir(parents=True, exist_ok=True)

    # ディレクトリを作成
    for i in range(num_dirs):
        dir_path = base_path / f"dir_{i:04d}"
        dir_path.mkdir(exist_ok=True)

    # ファイルを作成
    for i in range(num_files):
        file_path = base_path / f"file_{i:04d}.txt"
        file_path.write_text(f"content_{i}", encoding="utf-8")

    return base_path


def create_flat_directory(
    base_path: Path,
    num_entries: int = 10000,
) -> Path:
    """
    フラットな大規模ディレクトリを作成

    Args:
        base_path: ベースパス
        num_entries: エントリ数（デフォルト: 10000）

    Returns:
        作成されたディレクトリのパス
    """
    base_path.mkdir(parents=True, exist_ok=True)

    # 半分はファイル、半分はディレクトリ
    num_files = num_entries // 2
    num_dirs = num_entries - num_files

    # ファイルを作成
    for i in range(num_files):
        file_path = base_path / f"file_{i:05d}.txt"
        file_path.write_text(f"content_{i}", encoding="utf-8")

    # ディレクトリを作成
    for i in range(num_dirs):
        dir_path = base_path / f"dir_{i:05d}"
        dir_path.mkdir(exist_ok=True)

    return base_path


def create_deep_directory_tree(
    base_path: Path,
    depth: int = 5,
    branching_factor: int = 10,
) -> Path:
    """
    深いディレクトリツリーを作成（go-to-path テスト用）

    Args:
        base_path: ベースパス
        depth: 深さ（デフォルト: 5）
        branching_factor: 各レベルの分岐数（デフォルト: 10）

    Returns:
        作成されたルートディレクトリのパス
    """
    base_path.mkdir(parents=True, exist_ok=True)

    def _create_level(current_path: Path, current_depth: int) -> None:
        if current_depth >= depth:
            return

        for i in range(branching_factor):
            dir_path = current_path / f"level_{current_depth}_dir_{i}"
            dir_path.mkdir(exist_ok=True)

            # 各ディレクトリにファイルを追加
            file_path = dir_path / f"file_{i}.txt"
            file_path.write_text(f"content_level_{current_depth}_{i}", encoding="utf-8")

            # 再帰的に次のレベルを作成
            _create_level(dir_path, current_depth + 1)

    _create_level(base_path, 0)
    return base_path


def create_large_file_set_with_content(
    base_path: Path,
    num_files: int = 1000,
    avg_file_size: int = 1024,  # 1KB
) -> Path:
    """
    リアルなファイルサイズを持つ大規模ファイルセットを作成

    Args:
        base_path: ベースパス
        num_files: ファイル数（デフォルト: 1000）
        avg_file_size: 平均ファイルサイズ（デフォルト: 1024 バイト）

    Returns:
        作成されたディレクトリのパス
    """
    base_path.mkdir(parents=True, exist_ok=True)

    # サンプルコンテンツ（約1KB）
    sample_content = "x" * avg_file_size

    for i in range(num_files):
        file_path = base_path / f"file_{i:05d}.txt"
        # ファイルサイズに少し変化を持たせる
        file_size = avg_file_size + (i % 100) * 10
        file_path.write_text(sample_content[:file_size], encoding="utf-8")

    return base_path


def create_mixed_directory_structure(
    base_path: Path,
    num_dirs: int = 100,
    num_files: int = 900,
    nest_depth: int = 3,
) -> Path:
    """
    混合ディレクトリ構造を作成（フラットとネストの組み合わせ）

    Args:
        base_path: ベースパス
        num_dirs: ディレクトリ数（デフォルト: 100）
        num_files: ファイル数（デフォルト: 900）
        nest_depth: ネストの深さ（デフォルト: 3）

    Returns:
        作成されたディレクトリのパス
    """
    base_path.mkdir(parents=True, exist_ok=True)

    # ルートレベルのファイルとディレクトリを作成
    root_files = num_files // 2
    root_dirs = num_dirs // 2

    for i in range(root_files):
        file_path = base_path / f"root_file_{i:04d}.txt"
        file_path.write_text(f"root_content_{i}", encoding="utf-8")

    # ネストされたディレクトリを作成
    for i in range(root_dirs):
        dir_path = base_path / f"root_dir_{i:04d}"
        dir_path.mkdir(exist_ok=True)

        # 各ディレクトリにファイルを追加
        files_per_dir = (num_files - root_files) // root_dirs
        for j in range(files_per_dir):
            file_path = dir_path / f"nested_file_{j:04d}.txt"
            file_path.write_text(f"nested_content_{i}_{j}", encoding="utf-8")

    return base_path


def create_benchmark_state(
    num_entries: int = 1000,
) -> list[dict]:
    """
    ベンチマーク用の状態エントリを作成

    Args:
        num_entries: エントリ数（デフォルト: 1000）

    Returns:
        DirectoryEntryState の辞書リスト
    """
    entries = []
    num_dirs = num_entries // 5
    num_files = num_entries - num_dirs

    # ディレクトリエントリ
    for i in range(num_dirs):
        entries.append(
            entry(
                path=f"/test/dir_{i:04d}",
                kind="directory",
                name=f"dir_{i:04d}",
                hidden=False,
            ).__dict__
        )

    # ファイルエントリ
    for i in range(num_files):
        entries.append(
            entry(
                path=f"/test/file_{i:04d}.txt",
                kind="file",
                name=f"file_{i:04d}.txt",
                hidden=i % 10 == 0,  # 10% を隠しファイルに
                size_bytes=1024 + i,
            ).__dict__
        )

    return entries
