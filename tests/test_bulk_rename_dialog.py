from zivo.models import BulkRenameDialogState, BulkRenameRowViewState
from zivo.ui.bulk_rename_dialog import BulkRenameDialog


def test_bulk_rename_rows_render_editing_rich_text_without_format_error() -> None:
    state = BulkRenameDialogState(
        title="Rename 1 item",
        rows=(
            BulkRenameRowViewState(
                old_name="README.md",
                new_name="README.mda",
                status="ready",
                selected=True,
                editing=True,
                cursor_pos=10,
            ),
        ),
        find_text="",
        replace_text="",
        active_field="table",
        summary="1 changes · 0 unchanged · 0 errors",
        apply_enabled=True,
    )

    rendered = BulkRenameDialog._render_rows(state)

    assert "README.mda_" in rendered.plain
    assert "Ready" in rendered.plain
