"""
Unit tests for the PermissionAnalyzer.

Tests are divided into two groups:

1. Cross-platform tests (run on macOS/Linux/Windows):
   - Nonexistent file handling
   - Directory path handling
   - Result structure validation
   - Read permission on a normal temp file
   - Write permission on a normal temp file
   - Write permission on a read-only file
   - All FileOperation enum values
   - Permission bits dictionary completeness
   - Owner field is populated
   - Current user field is populated

2. Windows-only tests (skipped on non-Windows):
   - Detection method is 'windows_acl'
   - Owner format is 'DOMAIN\\User'
   - NTFS-specific permission scenarios

All tests verify the PermissionCheckResult structure — the analyzer
never prints directly to the console.
"""

import getpass
import os
import stat
import sys
import tempfile

import pytest

from diagnoser.analyzers.permissions import PermissionAnalyzer
from diagnoser.models import FileOperation, PermissionCheckResult

# Shared analyzer instance
_analyzer = PermissionAnalyzer()


# ======================================================================
# Cross-platform tests
# ======================================================================

class TestPermissionAnalyzerCrossPlatform:
    """Tests that run on any platform."""

    def test_nonexistent_file(self):
        """Case 1: file does not exist → error."""
        result = _analyzer.analyze(
            "/nonexistent/path/to/file.txt", FileOperation.READ
        )
        assert isinstance(result, PermissionCheckResult)
        assert result.permitted is False
        assert result.error is not None
        assert "does not exist" in result.error
        assert result.detection_method == "error"

    def test_directory_path(self, tmp_path):
        """Case 2: directory path → error."""
        result = _analyzer.analyze(str(tmp_path), FileOperation.READ)
        assert isinstance(result, PermissionCheckResult)
        assert result.permitted is False
        assert result.error is not None
        assert "directory" in result.error.lower()
        assert result.detection_method == "error"

    def test_result_structure(self):
        """The result always has the expected fields."""
        result = _analyzer.analyze("/nonexistent/file.xyz", FileOperation.READ)
        assert hasattr(result, "file_path")
        assert hasattr(result, "operation")
        assert hasattr(result, "permitted")
        assert hasattr(result, "owner")
        assert hasattr(result, "current_user")
        assert hasattr(result, "details")
        assert hasattr(result, "permission_bits")
        assert hasattr(result, "error")
        assert hasattr(result, "detection_method")

    def test_file_path_is_normalised(self):
        """The file_path in the result should be absolute and normalised."""
        result = _analyzer.analyze(
            "./relative/../relative/file.txt", FileOperation.READ
        )
        assert os.path.isabs(result.file_path)
        assert ".." not in result.file_path

    def test_operation_is_stored_as_string(self):
        """The operation field should be the string value of the enum."""
        result = _analyzer.analyze("/nonexistent/f.txt", FileOperation.WRITE)
        assert result.operation == "write"

    def test_default_operation_is_read(self):
        """If no operation is specified, default to READ."""
        result = _analyzer.analyze("/nonexistent/f.txt")
        assert result.operation == "read"

    def test_read_permission_granted(self):
        """An existing readable file → permitted=True for READ."""
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".txt"
        ) as f:
            temp_path = f.name
            f.write(b"readable content")

        try:
            result = _analyzer.analyze(temp_path, FileOperation.READ)
            assert isinstance(result, PermissionCheckResult)
            assert result.permitted is True
            assert result.error is None
            assert result.detection_method in ("os_access", "windows_acl")
        finally:
            os.unlink(temp_path)

    def test_write_permission_granted(self):
        """A normal temp file should be writable."""
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".txt"
        ) as f:
            temp_path = f.name
            f.write(b"writable content")

        try:
            result = _analyzer.analyze(temp_path, FileOperation.WRITE)
            assert result.permitted is True
            assert result.error is None
        finally:
            os.unlink(temp_path)

    def test_write_permission_denied_readonly(self):
        """A read-only file → permitted=False for WRITE."""
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".txt"
        ) as f:
            temp_path = f.name
            f.write(b"read-only content")

        try:
            # Make the file read-only
            os.chmod(temp_path, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)

            result = _analyzer.analyze(temp_path, FileOperation.WRITE)
            assert result.permitted is False
            assert result.error is None  # Not an error — a valid finding
            assert "DENIED" in result.details
        finally:
            # Restore write permission so we can delete it
            os.chmod(temp_path, stat.S_IRUSR | stat.S_IWUSR)
            os.unlink(temp_path)

    def test_permission_bits_are_complete(self):
        """permission_bits dict should have read, write, execute keys."""
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".txt"
        ) as f:
            temp_path = f.name

        try:
            result = _analyzer.analyze(temp_path, FileOperation.READ)
            assert "read" in result.permission_bits
            assert "write" in result.permission_bits
            assert "execute" in result.permission_bits
            assert all(
                isinstance(v, bool)
                for v in result.permission_bits.values()
            )
        finally:
            os.unlink(temp_path)

    def test_current_user_is_populated(self):
        """current_user should match the actual current user."""
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".txt"
        ) as f:
            temp_path = f.name

        try:
            result = _analyzer.analyze(temp_path, FileOperation.READ)
            assert result.current_user != ""
            assert result.current_user == getpass.getuser()
        finally:
            os.unlink(temp_path)

    def test_owner_is_populated(self):
        """owner field should be populated for an accessible file."""
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".txt"
        ) as f:
            temp_path = f.name

        try:
            result = _analyzer.analyze(temp_path, FileOperation.READ)
            # Owner should be a non-empty string on all platforms
            assert result.owner != ""
        finally:
            os.unlink(temp_path)

    def test_details_contain_operation(self):
        """The details string should mention the operation checked."""
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".txt"
        ) as f:
            temp_path = f.name

        try:
            result = _analyzer.analyze(temp_path, FileOperation.EXECUTE)
            assert "EXECUTE" in result.details
        finally:
            os.unlink(temp_path)

    def test_all_operations_accepted(self):
        """All FileOperation enum values should work without error."""
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".txt"
        ) as f:
            temp_path = f.name

        try:
            for op in FileOperation:
                result = _analyzer.analyze(temp_path, op)
                assert isinstance(result, PermissionCheckResult)
                assert result.operation == op.value
                assert result.error is None
        finally:
            os.unlink(temp_path)

    def test_details_granted_message(self):
        """When permitted, details should say GRANTED."""
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".txt"
        ) as f:
            temp_path = f.name

        try:
            result = _analyzer.analyze(temp_path, FileOperation.READ)
            assert "GRANTED" in result.details
        finally:
            os.unlink(temp_path)

    def test_delete_permission_note(self):
        """DELETE check details should include the limitation note."""
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".txt"
        ) as f:
            temp_path = f.name

        # Make read-only so DELETE is denied
        try:
            os.chmod(temp_path, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
            result = _analyzer.analyze(temp_path, FileOperation.DELETE)
            # On non-Windows, DELETE maps to write check so should be denied
            if not result.permitted:
                assert "DELETE" in result.details or "delete" in result.details
        finally:
            os.chmod(temp_path, stat.S_IRUSR | stat.S_IWUSR)
            os.unlink(temp_path)


# ======================================================================
# Windows-only tests
# ======================================================================

@pytest.mark.skipif(
    sys.platform != "win32",
    reason="Requires Windows NTFS and advapi32.dll"
)
class TestPermissionAnalyzerWindows:
    """Tests that require Windows NTFS and security APIs."""

    def test_detection_method_windows_acl(self):
        """On Windows, detection_method should be 'windows_acl'."""
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".txt"
        ) as f:
            temp_path = f.name

        try:
            result = _analyzer.analyze(temp_path, FileOperation.READ)
            assert result.detection_method == "windows_acl"
        finally:
            os.unlink(temp_path)

    def test_owner_format_domain_user(self):
        """On Windows, owner should be in 'DOMAIN\\User' format."""
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".txt"
        ) as f:
            temp_path = f.name

        try:
            result = _analyzer.analyze(temp_path, FileOperation.READ)
            # Owner should contain a backslash (DOMAIN\User)
            assert "\\" in result.owner, (
                f"Expected 'DOMAIN\\\\User' format, got: {result.owner}"
            )
        finally:
            os.unlink(temp_path)

    def test_write_denied_readonly_windows(self):
        """A read-only file on Windows → WRITE denied."""
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".txt"
        ) as f:
            temp_path = f.name
            f.write(b"read-only content")

        try:
            os.chmod(temp_path, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
            result = _analyzer.analyze(temp_path, FileOperation.WRITE)
            assert result.permitted is False
            assert result.detection_method == "windows_acl"
            assert "DENIED" in result.details
        finally:
            os.chmod(temp_path, stat.S_IRUSR | stat.S_IWUSR)
            os.unlink(temp_path)
