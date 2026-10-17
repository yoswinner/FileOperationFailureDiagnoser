"""
Unit tests for the FileAttributeAnalyzer.

Tests are divided into two groups:
1. Cross-platform tests (run on macOS/Linux/Windows):
   - Nonexistent file handling
   - Directory path handling
   - Result structure validation
   - Path normalisation
   - Analysis does not modify target file
   - Read-only attribute detection
   - Bitmask flag decoding (system, archive, reparse_point, offline) via controlled tests
   - Graceful structured error handling on OS exceptions

2. Windows-only tests:
   - Native Windows attribute detection (windows_stat)
   - Hidden file detection with verified cleanup
   - Read-only file detection on Windows with verified cleanup
"""

import os
import stat
import sys
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from diagnoser.analyzers.file_attributes import (
    FILE_ATTRIBUTE_ARCHIVE,
    FILE_ATTRIBUTE_HIDDEN,
    FILE_ATTRIBUTE_OFFLINE,
    FILE_ATTRIBUTE_READONLY,
    FILE_ATTRIBUTE_REPARSE_POINT,
    FILE_ATTRIBUTE_SYSTEM,
    FileAttributeAnalyzer,
)
from diagnoser.models import FileAttributeResult

# Shared analyzer instance
_analyzer = FileAttributeAnalyzer()


# ======================================================================
# Cross-platform tests
# ======================================================================

class TestFileAttributeAnalyzerCrossPlatform:
    """Tests that run reliably on all platforms."""

    def test_nonexistent_file(self):
        """Nonexistent file should return a structured error result."""
        result = _analyzer.analyze("/nonexistent/file/path/here.txt")

        assert isinstance(result, FileAttributeResult)
        assert result.error is not None
        assert "does not exist" in result.error
        assert result.detection_method == "error"
        assert result.is_readonly is None

    def test_directory_path(self, tmp_path):
        """Directory path should be rejected cleanly with a structured error."""
        result = _analyzer.analyze(str(tmp_path))

        assert isinstance(result, FileAttributeResult)
        assert result.error is not None
        assert "directory" in result.error.lower()
        assert result.detection_method == "error"

    def test_result_structure(self):
        """Result must contain all expected dataclass fields."""
        result = _analyzer.analyze("/nonexistent/test.xyz")

        assert hasattr(result, "file_path")
        assert hasattr(result, "is_readonly")
        assert hasattr(result, "is_hidden")
        assert hasattr(result, "is_system")
        assert hasattr(result, "is_archive")
        assert hasattr(result, "is_reparse_point")
        assert hasattr(result, "is_offline")
        assert hasattr(result, "raw_attributes")
        assert hasattr(result, "attributes_list")
        assert hasattr(result, "error")
        assert hasattr(result, "detection_method")

    def test_file_path_is_normalised(self):
        """The returned file_path must be absolute and normalised."""
        result = _analyzer.analyze("./relative/../relative/file.txt")
        assert os.path.isabs(result.file_path)
        assert ".." not in result.file_path

    def test_analysis_does_not_modify_file(self):
        """Attribute analysis must be strictly read-only and never alter file content or mtime."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            temp_path = f.name
            f.write(b"Strictly read-only test data")

        try:
            stat_before = os.stat(temp_path)
            with open(temp_path, "rb") as f:
                content_before = f.read()

            result = _analyzer.analyze(temp_path)
            assert result.error is None

            stat_after = os.stat(temp_path)
            with open(temp_path, "rb") as f:
                content_after = f.read()

            assert content_before == content_after
            assert stat_before.st_size == stat_after.st_size
            assert stat_before.st_mtime == stat_after.st_mtime
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_readonly_attribute_detection(self):
        """A file with read-only permissions should report is_readonly=True."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            temp_path = f.name
            f.write(b"read-only test")

        try:
            # Mark file read-only across platforms
            os.chmod(temp_path, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)

            result = _analyzer.analyze(temp_path)
            assert isinstance(result, FileAttributeResult)
            assert result.is_readonly is True
            assert "READONLY" in result.attributes_list
        finally:
            os.chmod(temp_path, stat.S_IRUSR | stat.S_IWUSR)
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_flag_decoding_combinations(self):
        """Controlled test verifying bitmask decoding for Windows attributes."""
        # Test combined bitmask: ARCHIVE (0x20) + SYSTEM (0x04) + HIDDEN (0x02) + READONLY (0x01)
        combined_mask = (
            FILE_ATTRIBUTE_ARCHIVE
            | FILE_ATTRIBUTE_SYSTEM
            | FILE_ATTRIBUTE_HIDDEN
            | FILE_ATTRIBUTE_READONLY
            | FILE_ATTRIBUTE_REPARSE_POINT
            | FILE_ATTRIBUTE_OFFLINE
        )

        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            temp_path = f.name

        try:
            # Mock the stat call to simulate combined Windows attributes
            mock_stat = MagicMock()
            mock_stat.st_file_attributes = combined_mask

            with patch("os.stat", return_value=mock_stat):
                result = FileAttributeAnalyzer._analyze_windows(temp_path)

            assert result.is_readonly is True
            assert result.is_hidden is True
            assert result.is_system is True
            assert result.is_archive is True
            assert result.is_reparse_point is True
            assert result.is_offline is True
            assert result.raw_attributes == combined_mask
            assert "READONLY" in result.attributes_list
            assert "HIDDEN" in result.attributes_list
            assert "SYSTEM" in result.attributes_list
            assert "ARCHIVE" in result.attributes_list
            assert "REPARSE_POINT" in result.attributes_list
            assert "OFFLINE" in result.attributes_list
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_permission_error_returns_structured_error(self):
        """Simulated permission error accessing attributes returns a structured error."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            temp_path = f.name

        try:
            with patch("os.stat", side_effect=PermissionError("Simulated access denial")):
                result = _analyzer.analyze(temp_path)

            assert isinstance(result, FileAttributeResult)
            assert result.error is not None
            assert "Permission denied" in result.error
            assert result.detection_method == "error"
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_unexpected_os_error_returns_structured_error(self):
        """Simulated unexpected OS error returns a structured error when both stat and API fail."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            temp_path = f.name

        try:
            with patch("diagnoser.analyzers.file_attributes._kernel32", None):
                with patch("os.stat", side_effect=OSError("Device I/O error")):
                    result = _analyzer.analyze(temp_path)

            assert isinstance(result, FileAttributeResult)
            assert result.error is not None
            assert result.detection_method == "error"
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


# ======================================================================
# Windows-only tests
# ======================================================================

@pytest.mark.skipif(
    sys.platform != "win32",
    reason="Requires Windows operating system"
)
class TestFileAttributeAnalyzerWindows:
    """Tests executing against the real Windows file system."""

    def test_windows_normal_file_attributes(self):
        """A normal temp file on Windows typically has the ARCHIVE attribute."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            temp_path = f.name
            f.write(b"Windows normal attributes test")

        try:
            result = _analyzer.analyze(temp_path)
            assert result.detection_method == "windows_stat"
            assert result.error is None
            assert isinstance(result.raw_attributes, int)
            assert result.is_readonly is False
            assert result.is_hidden is False
            assert result.is_system is False
            assert result.is_offline is False
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_windows_hidden_file_detection(self):
        """Test real detection of the HIDDEN attribute on Windows with guaranteed cleanup."""
        import ctypes
        kernel32 = ctypes.windll.kernel32

        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            temp_path = f.name
            f.write(b"Windows hidden test")

        try:
            # Set hidden attribute (FILE_ATTRIBUTE_HIDDEN = 0x02)
            ret = kernel32.SetFileAttributesW(temp_path, 0x02)
            assert ret != 0, "Failed to set hidden attribute on test file"

            result = _analyzer.analyze(temp_path)
            assert result.is_hidden is True
            assert "HIDDEN" in result.attributes_list
        finally:
            # Restore normal attribute before deletion (FILE_ATTRIBUTE_NORMAL = 0x80)
            kernel32.SetFileAttributesW(temp_path, 0x80)
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_windows_readonly_file_detection(self):
        """Test real detection of the READONLY attribute on Windows with guaranteed cleanup."""
        import ctypes
        kernel32 = ctypes.windll.kernel32

        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            temp_path = f.name
            f.write(b"Windows read-only test")

        try:
            # Set read-only attribute (FILE_ATTRIBUTE_READONLY = 0x01)
            ret = kernel32.SetFileAttributesW(temp_path, 0x01)
            assert ret != 0, "Failed to set read-only attribute on test file"

            result = _analyzer.analyze(temp_path)
            assert result.is_readonly is True
            assert "READONLY" in result.attributes_list
        finally:
            # Restore normal attribute before deletion
            kernel32.SetFileAttributesW(temp_path, 0x80)
            if os.path.exists(temp_path):
                os.unlink(temp_path)
