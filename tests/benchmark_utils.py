"""
ベンチマークユーティリティモジュール

再現可能なパフォーマンス測定のためのユーティリティ関数とデコレータを提供します。
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from functools import wraps
from importlib import import_module
from typing import Any, Callable


@dataclass
class BenchmarkResult:
    """ベンチマーク結果を表すデータクラス"""

    name: str
    """ベンチマーク名"""

    total_time: float
    """合計実行時間（秒）"""

    iterations: int
    """反復回数"""

    avg_time: float
    """平均実行時間（秒）"""

    min_time: float
    """最小実行時間（秒）"""

    max_time: float
    """最大実行時間（秒）"""

    def __str__(self) -> str:
        """人間が読みやすい文字列表現を返す"""
        return (
            f"{self.name}:\n"
            f"  Total: {self.total_time:.4f}s\n"
            f"  Iterations: {self.iterations}\n"
            f"  Average: {self.avg_time:.4f}s\n"
            f"  Min: {self.min_time:.4f}s\n"
            f"  Max: {self.max_time:.4f}s"
        )


def benchmark(
    *,
    iterations: int = 5,
    warmup: int = 1,
) -> Callable[[Callable[..., Any]], Callable[..., BenchmarkResult]]:
    """
    関数の実行時間を計測するデコレータ

    Args:
        iterations: 反復回数（デフォルト: 5）
        warmup: ウォームアップ回数（デフォルト: 1）

    Returns:
        ベンチマーク結果を返すデコレータ

    Examples:
        >>> @benchmark(iterations=10, warmup=2)
        ... def my_function():
        ...     return sum(range(1000))
        >>> result = my_function()
        >>> print(result)
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., BenchmarkResult]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> BenchmarkResult:
            # ウォームアップ（Python のキャッシュを考慮）
            for _ in range(warmup):
                func(*args, **kwargs)

            # 本計測
            times: list[float] = []
            for _ in range(iterations):
                start = time.perf_counter()
                func(*args, **kwargs)
                end = time.perf_counter()
                times.append(end - start)

            # 統計計算
            total_time = sum(times)
            avg_time = total_time / iterations
            min_time = min(times)
            max_time = max(times)

            return BenchmarkResult(
                name=func.__name__,
                total_time=total_time,
                iterations=iterations,
                avg_time=avg_time,
                min_time=min_time,
                max_time=max_time,
            )

        return wrapper

    return decorator


def measure_import_time(module_name: str, iterations: int = 5) -> BenchmarkResult:
    """
    モジュールのインポート時間を計測

    Args:
        module_name: インポートするモジュール名
        iterations: 反復回数（デフォルト: 5）

    Returns:
        ベンチマーク結果

    Examples:
        >>> result = measure_import_time("peneo")
        >>> print(result)
    """
    times: list[float] = []

    # ウォームアップ（最初の1回は除外）
    try:
        import_module(module_name)
    except ImportError:
        # モジュールが存在しない場合は0を返す
        pass

    for _ in range(iterations):
        # モジュールを再インポートするために、まず削除
        import sys
        if module_name in sys.modules:
            del sys.modules[module_name]

        start = time.perf_counter()
        import_module(module_name)
        end = time.perf_counter()
        times.append(end - start)

    # 統計計算
    total_time = sum(times)
    avg_time = total_time / iterations
    min_time = min(times)
    max_time = max(times)

    return BenchmarkResult(
        name=f"import_{module_name}",
        total_time=total_time,
        iterations=iterations,
        avg_time=avg_time,
        min_time=min_time,
        max_time=max_time,
    )


def measure_startup_time(
    command: list[str],
    iterations: int = 5,
) -> BenchmarkResult:
    """
    コマンドの起動時間を計測

    Args:
        command: 実行するコマンド（リスト形式）
        iterations: 反復回数（デフォルト: 5）

    Returns:
        ベンチマーク結果

    Examples:
        >>> result = measure_startup_time(["uv", "run", "peneo", "--help"])
        >>> print(result)
    """
    times: list[float] = []

    for _ in range(iterations):
        start = time.perf_counter()
        subprocess.run(
            command,
            capture_output=True,
            check=True,
        )
        end = time.perf_counter()
        times.append(end - start)

    # 統計計算
    total_time = sum(times)
    avg_time = total_time / iterations
    min_time = min(times)
    max_time = max(times)

    command_str = " ".join(command)
    return BenchmarkResult(
        name=f"startup_{command_str.replace(' ', '_')}",
        total_time=total_time,
        iterations=iterations,
        avg_time=avg_time,
        min_time=min_time,
        max_time=max_time,
    )
