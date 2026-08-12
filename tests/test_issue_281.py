from dataclasses import replace

from zivo.services import GoPathCompletionService
from zivo.state import (
    GoCompletionState,
    RunGoPathCompletionEffect,
    build_initial_app_state,
    reduce_app_state,
    select_command_palette_state,
)
from zivo.state.actions import (
    BeginGo,
    GoPathCompletionCompleted,
    SetCommandPaletteQuery,
)


def test_go_completion_service_uses_cached_listing_and_caps_results(tmp_path) -> None:
    for name in ("docs", "downloads", "drafts"):
        (tmp_path / name).mkdir()
    (tmp_path / "notes.txt").write_text("notes")
    service = GoPathCompletionService(cache_ttl_seconds=60, max_results=2)

    first = service.complete("d", str(tmp_path))
    second = service.complete("do", str(tmp_path))

    assert first.paths == (
        str(tmp_path / "docs"),
        str(tmp_path / "downloads"),
    )
    assert first.truncated is True
    assert second.paths == (str(tmp_path / "docs"), str(tmp_path / "downloads"))
    assert second.truncated is False


def test_go_completion_service_honors_cancellation(tmp_path) -> None:
    (tmp_path / "directory").mkdir()
    service = GoPathCompletionService()

    result = service.complete("d", str(tmp_path), is_cancelled=lambda: True)

    assert result.paths == ()
    assert result.truncated is False


def test_go_query_schedules_async_completion_and_clears_stale_paths(tmp_path) -> None:
    state = reduce_app_state(build_initial_app_state(), BeginGo()).state
    first = reduce_app_state(state, SetCommandPaletteQuery("do"))

    assert first.effects == (
        RunGoPathCompletionEffect(
            request_id=1,
            query="do",
            base_path=state.current_path,
        ),
    )
    assert first.state.command_palette is not None
    assert first.state.command_palette.go_completion.loading is True
    assert first.state.pending_go_completion_request_id == 1

    completed = reduce_app_state(
        first.state,
        GoPathCompletionCompleted(
            request_id=1,
            query="do",
            paths=(str(tmp_path / "docs"),),
        ),
    ).state
    next_query = reduce_app_state(completed, SetCommandPaletteQuery("dr"))

    assert next_query.state.command_palette is not None
    assert next_query.state.command_palette.go_completion.paths == ()
    assert next_query.state.command_palette.go_completion.loading is True

    stale = reduce_app_state(
        next_query.state,
        GoPathCompletionCompleted(
            request_id=1,
            query="do",
            paths=(str(tmp_path / "stale"),),
        ),
    ).state
    assert stale == next_query.state


def test_go_view_distinguishes_loading_from_empty_results() -> None:
    state = reduce_app_state(build_initial_app_state(), BeginGo()).state
    state = replace(
        state,
        command_palette=replace(
            state.command_palette,
            go_completion=GoCompletionState(query="docs", loading=True),
        ),
    )

    view = select_command_palette_state(state)

    assert view is not None
    assert view.empty_message == "Searching directories…"
    assert view.footer_message is not None
    assert "Searching directories…" in view.footer_message
