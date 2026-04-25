"""On-demand filesystem attribute inspection service."""

from dataclasses import dataclass, field
from typing import Protocol

from zivo.adapters import DirectoryAttributeReader, LocalFilesystemAdapter
from zivo.state.models import AttributeInspectionState


class AttributeInspectionService(Protocol):
    """Boundary for loading detailed metadata for a single path."""

    def inspect(self, path: str) -> AttributeInspectionState: ...


@dataclass
class LiveAttributeInspectionService:
    """Load detailed attributes from the local filesystem on demand."""

    filesystem: DirectoryAttributeReader = field(default_factory=LocalFilesystemAdapter)

    def inspect(self, path: str) -> AttributeInspectionState:
        entry = self.filesystem.inspect_entry(path)
        if entry is None:
            raise FileNotFoundError(path)
        return AttributeInspectionState(
            name=entry.name,
            kind=entry.kind,
            path=entry.path,
            symlink=entry.symlink,
            size_bytes=entry.size_bytes,
            modified_at=entry.modified_at,
            hidden=entry.hidden,
            permissions_mode=entry.permissions_mode,
            owner=entry.owner,
            group=entry.group,
        )


@dataclass
class FakeAttributeInspectionService:
    """Test double for deterministic attribute inspection results."""

    inspections_by_path: dict[str, AttributeInspectionState] = field(default_factory=dict)
    errors_by_path: dict[str, Exception] = field(default_factory=dict)
    inspect_calls: list[str] = field(default_factory=list)

    def inspect(self, path: str) -> AttributeInspectionState:
        self.inspect_calls.append(path)
        if path in self.errors_by_path:
            raise self.errors_by_path[path]
        return self.inspections_by_path[path]
