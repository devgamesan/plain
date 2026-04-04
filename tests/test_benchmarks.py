"""
パフォーマンスベンチマークテストスイート

主要な操作のパフォーマンスを測定するベンチマークテストを提供します。
"""

import pytest

from peneo.adapters.filesystem import LocalFilesystemAdapter
from peneo.services.directory_size import DirectorySizeService
from peneo.state import (
    AppState,
    CommandPaletteSource,
    CommandPaletteState,
    build_initial_app_state,
)
from peneo.state.command_palette import get_command_palette_items
from peneo.state.reducer_common import list_matching_directory_paths
from peneo.state.selectors import select_shell_data
from tests.benchmark_fixtures import (
    create_deep_directory_tree,
    create_flat_directory,
    create_large_directory,
)
from tests.benchmark_utils import benchmark, measure_import_time, measure_startup_time


class TestStartupBenchmarks:
    """起動時間関連のベンチマーク"""

    def test_import_peneo(self):
        """peneo モジュールのインポート時間を測定"""
        result = measure_import_time("peneo", iterations=10)
        print(f"\n{result}")

        # Baseline: ~200ms (2026-04-04)
        # 許容範囲: 180-220ms (10%)
        assert result.avg_time < 0.220, f"Import time too slow: {result.avg_time:.4f}s"

    def test_startup_help(self):
        """peneo --help の起動時間を測定"""
        result = measure_startup_time(
            ["uv", "run", "peneo", "--help"],
            iterations=5,
        )
        print(f"\n{result}")

        # Baseline: ~200-245ms (2026-04-04)
        # 許容範囲: 270ms (10%)
        assert result.avg_time < 0.270, f"Help startup too slow: {result.avg_time:.4f}s"

    def test_startup_init_bash(self):
        """peneo init bash の起動時間を測定"""
        result = measure_startup_time(
            ["uv", "run", "peneo", "init", "bash"],
            iterations=5,
        )
        print(f"\n{result}")

        # Baseline: ~244ms (2026-04-04)
        # 許容範囲: 270ms (10%)
        assert result.avg_time < 0.270, f"Init bash startup too slow: {result.avg_time:.4f}s"


class TestDirectoryBenchmarks:
    """ディレクトリ操作関連のベンチマーク"""

    @pytest.mark.parametrize("num_entries", [1000, 5000, 10000])
    def test_list_directory_performance(self, tmp_path, num_entries):
        """ディレクトリスキャンのパフォーマンスを測定"""

        # テストデータを作成
        create_flat_directory(tmp_path / "test_dir", num_entries=num_entries)

        adapter = LocalFilesystemAdapter()

        @benchmark(iterations=10, warmup=2)
        def _list_directory():
            return adapter.list_directory(str(tmp_path / "test_dir"))

        result = _list_directory()
        print(f"\n{result}")

        # 期待値: 1k entries ~数ms、10k entries ~数十ms
        # 具体的な baseline は実行後に記録
        assert result.avg_time < 1.0, f"Directory listing too slow: {result.avg_time:.4f}s"

    def test_directory_size_batch_calculation(self, tmp_path):
        """ディレクトリサイズ計算のパフォーマンスを測定"""

        # テストデータを作成
        create_large_directory(tmp_path / "test_dir", num_dirs=100, num_files=400)

        adapter = LocalFilesystemAdapter()
        service = DirectorySizeService(adapter)

        @benchmark(iterations=5, warmup=1)
        def _calculate_sizes():
            # ディレクトリ内のファイルのサイズを計算
            entries = adapter.list_directory(str(tmp_path / "test_dir"))
            file_entries = [e for e in entries if e.kind == "file"]
            service.calculate_directory_sizes(
                tuple(e.path for e in file_entries[:10]),  # 最初の10ファイル
            )

        result = _calculate_sizes()
        print(f"\n{result}")

        # ディレクトリサイズ計算はコストが高いので許容範囲を広く設定
        assert result.avg_time < 5.0, f"Directory size calculation too slow: {result.avg_time:.4f}s"


class TestSelectorBenchmarks:
    """セレクタ関連のベンチマーク"""

    @pytest.mark.parametrize("num_entries", [1000, 10000])
    def test_select_shell_data_performance(self, tmp_path, num_entries):
        """select_shell_data のパフォーマンスを測定"""

        # テストデータを作成
        create_flat_directory(tmp_path / "test_dir", num_entries=num_entries)

        # 初期状態を構築
        state = build_initial_app_state(str(tmp_path / "test_dir"))

        @benchmark(iterations=100, warmup=10)
        def _select_shell_data():
            return select_shell_data(state)

        result = _select_shell_data()
        print(f"\n{result}")

        # Baseline: 10k entries ~4.2ms/call (2026-04-04)
        # 許容範囲: 5ms (約20%)
        if num_entries == 10000:
            assert result.avg_time < 0.005, f"select_shell_data too slow: {result.avg_time:.4f}s"

    @pytest.mark.parametrize("num_siblings", [1000, 5000])
    def test_list_matching_directory_paths(self, tmp_path, num_siblings):
        """go-to-path 候補生成のパフォーマンスを測定"""

        # 深いディレクトリツリーを作成
        create_deep_directory_tree(
            tmp_path / "test_dir",
            depth=3,
            branching_factor=num_siblings // 27,  # 約 num_siblings 個のディレクトリ
        )

        @benchmark(iterations=50, warmup=5)
        def _list_matching_paths():
            return list_matching_directory_paths("dir", str(tmp_path / "test_dir"))

        result = _list_matching_paths()
        print(f"\n{result}")

        # Baseline: 5k sibling dirs ~33ms (2026-04-04)
        # 許容範囲: 40ms (約20%)
        if num_siblings == 5000:
            assert (
                result.avg_time < 0.040
            ), f"list_matching_directory_paths too slow: {result.avg_time:.4f}s"

    @pytest.mark.parametrize("num_candidates", [1000, 5000])
    def test_command_palette_item_generation(self, tmp_path, num_candidates):
        """コマンドパレットアイテム生成のパフォーマンスを測定"""

        # テストデータを作成
        create_flat_directory(tmp_path / "test_dir", num_entries=num_candidates)

        # go-to-path ソースのコマンドパレット状態を作成
        state = build_initial_app_state(str(tmp_path / "test_dir"))

        # go_to_path_candidates を設定
        candidates = tuple(
            str(tmp_path / "test_dir" / f"dir_{i:05d}")
            for i in range(min(num_candidates, 100))
        )

        # ディレクトリを作成
        for candidate in candidates:
            candidate_path = candidate
            if "dir_" in candidate_path:
                try:
                    candidate_path.mkdir(exist_ok=True)
                except (OSError, FileNotFoundError):
                    pass

        state = AppState(
            **{
                **state.__dict__,
                "command_palette": CommandPaletteState(
                    source=CommandPaletteSource.GO_TO_PATH,
                    query="",
                    file_search_results=(),
                    grep_search_results=(),
                    history_results=(),
                    go_to_path_candidates=candidates,
                ),
            }
        )

        @benchmark(iterations=100, warmup=10)
        def _get_command_palette_items():
            return get_command_palette_items(state)

        result = _get_command_palette_items()
        print(f"\n{result}")

        # Baseline: 5k candidates ~8.25ms/call (2026-04-04)
        # 許容範囲: 10ms (約20%)
        if num_candidates == 5000:
            assert (
                result.avg_time < 0.010
            ), f"get_command_palette_items too slow: {result.avg_time:.4f}s"


class TestSearchBenchmarks:
    """検索関連のベンチマーク"""

    def test_file_search_performance(self, tmp_path):
        """ファイル検索のパフォーマンスを測定"""

        # テストデータを作成
        create_large_directory(tmp_path / "test_dir", num_dirs=50, num_files=500)

        # ファイル検索の実装は非同期で行われるため、
        # ここでは基本的なパス検索のパフォーマンスを測定

        import os

        @benchmark(iterations=20, warmup=3)
        def _search_files():
            # 簡易的なファイル検索（glob パターン使用）
            matches = []
            for root, dirs, files in os.walk(str(tmp_path / "test_dir")):
                for file in files:
                    if "file_" in file:
                        matches.append(os.path.join(root, file))
            return matches

        result = _search_files()
        print(f"\n{result}")

        # ファイル検索は許容範囲を広く設定
        assert result.avg_time < 1.0, f"File search too slow: {result.avg_time:.4f}s"

    def test_grep_search_performance(self, tmp_path):
        """grep 検索のパフォーマンスを測定"""

        # テストデータを作成
        create_large_directory(tmp_path / "test_dir", num_dirs=50, num_files=500)

        # grep 検索の代わりに、基本的な文字列検索を測定

        @benchmark(iterations=20, warmup=3)
        def _search_content():
            # 簡易的なコンテンツ検索
            matches = 0
            for entry in (tmp_path / "test_dir").rglob("*.txt"):
                try:
                    content = entry.read_text(encoding="utf-8")
                    if "content_" in content:
                        matches += 1
                except (OSError, UnicodeDecodeError):
                    pass
            return matches

        result = _search_content()
        print(f"\n{result}")

        # コンテンツ検索は許容範囲を広く設定
        assert result.avg_time < 2.0, f"Grep search too slow: {result.avg_time:.4f}s"


# CI 向けの簡易ベンチマーク（高速実行）
class TestQuickBenchmarks:
    """CI で実行する高速ベンチマーク"""

    def test_quick_startup(self):
        """起動時間の簡易測定"""
        result = measure_startup_time(
            ["uv", "run", "peneo", "--help"],
            iterations=3,
        )
        print(f"\n{result}")
        assert result.avg_time < 0.300

    def test_quick_directory_operations(self, tmp_path):
        """ディレクトリ操作の簡易測定"""
        create_flat_directory(tmp_path / "test_dir", num_entries=1000)

        adapter = LocalFilesystemAdapter()

        @benchmark(iterations=5, warmup=1)
        def _list_directory():
            return adapter.list_directory(str(tmp_path / "test_dir"))

        result = _list_directory()
        print(f"\n{result}")
        assert result.avg_time < 0.5

    def test_quick_selector_performance(self, tmp_path):
        """セレクタの簡易測定"""
        create_flat_directory(tmp_path / "test_dir", num_entries=1000)
        state = build_initial_app_state(str(tmp_path / "test_dir"))

        @benchmark(iterations=50, warmup=5)
        def _select_shell_data():
            return select_shell_data(state)

        result = _select_shell_data()
        print(f"\n{result}")
        assert result.avg_time < 0.005
