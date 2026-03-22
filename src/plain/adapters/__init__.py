"""External system adapters."""

from .filesystem import DirectoryReader, LocalFilesystemAdapter

__all__ = ["DirectoryReader", "LocalFilesystemAdapter"]
