from pathlib import Path

from zivo import create_app
from zivo.models import BulkRenameTarget
from zivo.state.actions import BeginBulkRename


async def test_bulk_rename_uses_base_name_and_central_focus_cycle(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "b.md").write_text("b")

    app = create_app(initial_path=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.dispatch_actions(
            (
                BeginBulkRename(
                    parent_dir=str(tmp_path),
                    targets=(
                        BulkRenameTarget(str(tmp_path / "a.txt"), "a.txt"),
                        BulkRenameTarget(str(tmp_path / "b.md"), "b.md"),
                    ),
                ),
            )
        )
        await pilot.pause()

        dialog = app.query_one("#bulk-rename-dialog")
        assert not dialog.query("#bulk-rename-find")
        assert not dialog.query("#bulk-rename-replace")
        assert not dialog.query("#bulk-rename-replace-action")
        assert app._app_state.bulk_rename is not None
        assert app._app_state.bulk_rename.active_field == "base_name"
        assert "> Base name: _" in app.query_one(
            "#bulk-rename-base-name"
        ).renderable.plain

        await pilot.press("p", "r", "o", "j", "e", "c", "t")
        await pilot.pause()
        assert app._app_state.bulk_rename is not None
        assert tuple(
            item.new_name for item in app._app_state.bulk_rename.items
        ) == ("project_1.txt", "project_2.md")

        await pilot.press("tab")
        await pilot.pause()
        assert app._app_state.bulk_rename.active_field == "base_name"
