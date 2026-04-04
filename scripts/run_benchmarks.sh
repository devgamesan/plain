#!/bin/bash
# ベンチマーク実行スクリプト
#
# 使用方法:
#   ./scripts/run_benchmarks.sh              # 全ベンチマークを実行
#   ./scripts/run_benchmarks.sh -k startup  # 起動時間のみ実行
#   ./scripts/run_benchmarks.sh -v          # 詳細出力

set -e

# スクリプトのディレクトリを取得
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# プロジェクトルートに移動
cd "$PROJECT_ROOT"

# ベンチマークを実行
echo "Running benchmarks..."
echo "Project root: $PROJECT_ROOT"
echo ""

uv run pytest tests/test_benchmarks.py -v --durations=0 --tb=short "$@"
