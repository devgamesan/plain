"""Canonical paths for deterministic state fixtures.

These are string values represented by ``build_initial_app_state``; tests do
not create or modify these locations. Real filesystem tests should use
pytest's ``tmp_path`` fixture instead.
"""

TEST_HOME = "/home/tadashi"
TEST_DEVELOP_ROOT = f"{TEST_HOME}/develop"
TEST_PROJECT_ROOT = f"{TEST_DEVELOP_ROOT}/zivo"

__all__ = ["TEST_DEVELOP_ROOT", "TEST_HOME", "TEST_PROJECT_ROOT"]
