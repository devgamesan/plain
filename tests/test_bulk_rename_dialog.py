from zivo.models import BulkRenameDialogState, BulkRenameRowViewState
from zivo.ui.bulk_rename_dialog import BulkRenameDialog


def test_bulk_rename_rows_render_review_names_without_table_editing() -> None:
    state = BulkRenameDialogState(
        title="Rename 2 selected items",
        rows=(
            BulkRenameRowViewState(
                old_name="README.md",
                new_name="project 1.md",
                status="ready",
            ),
        ),
        base_name="project",
        active_field="base_name",
        summary="1 changes · 0 unchanged · 0 errors",
        apply_enabled=True,
    )

    rendered = BulkRenameDialog._render_rows(state)

    assert "project 1.md" in rendered.plain
    assert "Ready" in rendered.plain


def test_bulk_rename_focus_marker_is_visible_for_base_name() -> None:
    rendered = BulkRenameDialog._render_field("Base name", "project", True)

    assert rendered.plain == "> Base name: project_"


def test_bulk_rename_action_buttons_do_not_join_native_focus_order() -> None:
    button = BulkRenameDialog._action_button("Rename items", "bulk-rename-apply")

    assert button.can_focus is False
