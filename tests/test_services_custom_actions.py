from pathlib import Path

from zivo.models import (
    CustomActionConfig,
    CustomActionContext,
    CustomActionExecutionRequest,
    CustomActionExpansionError,
    ShellCommandResult,
    custom_action_matches,
    expand_custom_action,
)
from zivo.services import LiveCustomActionService


def test_custom_action_matches_single_file_by_extension() -> None:
    action = CustomActionConfig(
        name="Optimize PNG",
        command=("oxipng", "{file}"),
        when="single_file",
        extensions=("png",),
    )

    assert custom_action_matches(
        action,
        CustomActionContext(
            cwd="/tmp/project",
            focused_file="/tmp/project/image.png",
        ),
    )
    assert not custom_action_matches(
        action,
        CustomActionContext(
            cwd="/tmp/project",
            focused_file="/tmp/project/notes.txt",
        ),
    )


def test_expand_custom_action_expands_file_and_cwd_placeholders() -> None:
    action = CustomActionConfig(
        name="Describe file",
        command=("tool", "{name}", "{stem}", "{ext}", "{cwd_basename}"),
        when="single_file",
        cwd="{cwd}",
    )

    request = expand_custom_action(
        action,
        CustomActionContext(
            cwd="/tmp/project",
            focused_file="/tmp/project/report.md",
        ),
    )

    assert request.command == ("tool", "report.md", "report", "md", "project")
    assert request.cwd == str(Path("/tmp/project").resolve(strict=False))


def test_expand_custom_action_expands_selection_as_multiple_arguments() -> None:
    action = CustomActionConfig(
        name="Archive selection",
        command=("tar", "-czf", "{cwd_basename}.tar.gz", "{selection}"),
        when="selection",
    )

    request = expand_custom_action(
        action,
        CustomActionContext(
            cwd="/tmp/project",
            selection=("/tmp/project/a.txt", "/tmp/project/b.txt"),
        ),
    )

    assert request.command == (
        "tar",
        "-czf",
        "project.tar.gz",
        "/tmp/project/a.txt",
        "/tmp/project/b.txt",
    )


def test_expand_custom_action_rejects_embedded_selection() -> None:
    action = CustomActionConfig(
        name="Bad selection",
        command=("echo", "files={selection}"),
        when="selection",
    )

    try:
        expand_custom_action(
            action,
            CustomActionContext(cwd="/tmp/project", selection=("/tmp/project/a.txt",)),
        )
    except CustomActionExpansionError as error:
        assert "{selection} must be a standalone command argument" in str(error)
    else:
        raise AssertionError("expected CustomActionExpansionError")


def test_live_custom_action_uses_shared_bounded_contract(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured.update(kwargs)
        return ShellCommandResult(exit_code=0, stdout="done\n")

    monkeypatch.setattr("zivo.services.custom_actions.run_bounded_process", fake_run)
    service = LiveCustomActionService()
    request = CustomActionExecutionRequest(
        name="Check",
        command=("tool", "--check"),
        cwd=str(tmp_path),
        mode="background",
    )
    def cancel_callback() -> bool:
        return False

    result = service.execute(
        request,
        max_output_bytes=2048,
        timeout_seconds=45,
        cancel_callback=cancel_callback,
    )

    assert result.result == ShellCommandResult(exit_code=0, stdout="done\n")
    assert captured["command"] == ["tool", "--check"]
    assert captured["cwd"] == str(tmp_path.resolve())
    assert captured["max_output_bytes"] == 2048
    assert captured["timeout_seconds"] == 45
    assert captured["cancel_callback"] is cancel_callback
