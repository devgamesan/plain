from zivo.archive_utils import (
    default_extract_destination,
    detect_archive_format,
    is_supported_archive_path,
    strip_archive_suffix,
)


class TestDetectArchiveFormat:
    def test_gz(self):
        assert detect_archive_format("file.log.gz") == "gz"

    def test_bz2(self):
        assert detect_archive_format("file.log.bz2") == "bz2"

    def test_tar_gz_not_matched_as_gz(self):
        assert detect_archive_format("archive.tar.gz") == "tar.gz"

    def test_tar_bz2_not_matched_as_bz2(self):
        assert detect_archive_format("archive.tar.bz2") == "tar.bz2"

    def test_zip(self):
        assert detect_archive_format("archive.zip") == "zip"

    def test_tar(self):
        assert detect_archive_format("archive.tar") == "tar"

    def test_unsupported(self):
        assert detect_archive_format("file.rar") is None

    def test_case_insensitive(self):
        assert detect_archive_format("FILE.LOG.GZ") == "gz"


class TestIsSupportedArchivePath:
    def test_gz_is_supported(self):
        assert is_supported_archive_path("dmesg.1.gz") is True

    def test_bz2_is_supported(self):
        assert is_supported_archive_path("dmesg.1.bz2") is True

    def test_unsupported_not_supported(self):
        assert is_supported_archive_path("file.rar") is False


class TestStripArchiveSuffix:
    def test_gz(self):
        assert strip_archive_suffix("dmesg.1.gz") == "dmesg.1"

    def test_bz2(self):
        assert strip_archive_suffix("dmesg.1.bz2") == "dmesg.1"

    def test_tar_gz(self):
        assert strip_archive_suffix("archive.tar.gz") == "archive"

    def test_zip(self):
        assert strip_archive_suffix("archive.zip") == "archive"


class TestDefaultExtractDestination:
    def test_gz_returns_parent_directory(self, tmp_path):
        archive_path = tmp_path / "dmesg.1.gz"
        archive_path.write_text("")

        result = default_extract_destination(str(archive_path))
        assert result == str(tmp_path)

    def test_bz2_returns_parent_directory(self, tmp_path):
        archive_path = tmp_path / "dmesg.1.bz2"
        archive_path.write_text("")

        result = default_extract_destination(str(archive_path))
        assert result == str(tmp_path)

    def test_tar_gz_returns_subdirectory(self, tmp_path):
        archive_path = tmp_path / "archive.tar.gz"
        archive_path.write_text("")

        result = default_extract_destination(str(archive_path))
        assert result == str(tmp_path / "archive")

    def test_zip_returns_subdirectory(self, tmp_path):
        archive_path = tmp_path / "archive.zip"
        archive_path.write_text("")

        result = default_extract_destination(str(archive_path))
        assert result == str(tmp_path / "archive")
