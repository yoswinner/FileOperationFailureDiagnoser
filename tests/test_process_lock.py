"""
Unit tests for the ProcessLockAnalyzer.

Tests are divided into two groups:

1. Cross-platform tests (run on macOS/Linux/Windows):
   - Nonexistent file handling
   - Directory path handling
   - Unlocked file handling (non-Windows: checks unsupported_platform)
   - Result structure validation

2. Windows-only tests (skipped on non-Windows):
   - Actual lock detection via Restart Manager
   - Detection of a file locked by a subprocess

All tests use the LockDetectionResult structured output — the
analyzer never prints directly to the console.
"""

import os
import sys
import tempfile

import pytest

from diagnoser.analyzers.process_lock import ProcessLockAnalyzer
from diagnoser.models import LockDetectionResult, ProcessInfo

# Shared analyzer instance
_analyzer = ProcessLockAnalyzer()


# ======================================================================
# Cross-platform tests
# ======================================================================

class TestProcessLockAnalyzerCrossPlatform:
    """Tests that run on any platform."""

    def test_nonexistent_file(self):
        """Case 1: file does not exist → error, is_locked=False."""
        result = _analyzer.analyze("/nonexistent/path/to/file.txt")

        assert isinstance(result, LockDetectionResult)
        assert result.is_locked is False
        assert result.error is not None
        assert "does not exist" in result.error
        assert result.detection_method == "error"
        assert result.processes == []

    def test_directory_path(self, tmp_path):
        """A directory path should be rejected cleanly."""
        result = _analyzer.analyze(str(tmp_path))

        assert isinstance(result, LockDetectionResult)
        assert result.is_locked is False
        assert result.error is not None
        assert "directory" in result.error.lower()
        assert result.detection_method == "error"

    def test_result_structure(self):
        """The result always has the expected fields."""
        result = _analyzer.analyze("/nonexistent/file.xyz")

        assert hasattr(result, "file_path")
        assert hasattr(result, "is_locked")
        assert hasattr(result, "processes")
        assert hasattr(result, "error")
        assert hasattr(result, "detection_method")

    def test_file_path_is_normalised(self):
        """The file_path in the result should be absolute and normalised."""
        result = _analyzer.analyze("./relative/../relative/file.txt")
        assert os.path.isabs(result.file_path)
        assert ".." not in result.file_path

    def test_unlocked_temp_file(self):
        """An existing, closed file should not be reported as locked.

        On non-Windows platforms, we get 'unsupported_platform' which
        also has is_locked=False.  On Windows, the Restart Manager
        confirms the file is not locked.
        """
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            temp_path = f.name
            f.write(b"test content")

        try:
            result = _analyzer.analyze(temp_path)
            assert isinstance(result, LockDetectionResult)
            assert result.is_locked is False
            # On macOS/Linux: detection_method is 'unsupported_platform'
            # On Windows: detection_method is 'restart_manager'
            assert result.detection_method in (
                "unsupported_platform", "restart_manager"
            )
        finally:
            os.unlink(temp_path)

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="Non-Windows platform check only"
    )
    def test_unsupported_platform_message(self):
        """On non-Windows, the error should explain the limitation."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            temp_path = f.name

        try:
            result = _analyzer.analyze(temp_path)
            assert result.detection_method == "unsupported_platform"
            assert "Restart Manager" in result.error
        finally:
            os.unlink(temp_path)


# ======================================================================
# Windows-only tests
# ======================================================================

@pytest.mark.skipif(
    sys.platform != "win32",
    reason="Requires Windows Restart Manager API"
)
class TestProcessLockAnalyzerWindows:
    """Tests that require the Windows Restart Manager."""

    def test_unlocked_file_windows(self):
        """Case 2: existing file with no locks → is_locked=False."""
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".txt"
        ) as f:
            temp_path = f.name
            f.write(b"unlocked content")

        try:
            result = _analyzer.analyze(temp_path)
            assert result.is_locked is False
            assert result.detection_method == "restart_manager"
            assert result.processes == []
            assert result.error is None
        finally:
            os.unlink(temp_path)

    def test_locked_file_detected(self):
        """Case 3: file held open → is_locked=True with process info.

        We hold the file open ourselves so the Restart Manager should
        detect at least one process (this Python process).
        """
        import subprocess

        # Create a file and hold it open via a subprocess
        temp_path = os.path.join(
            tempfile.gettempdir(), "diagnoser_lock_test.txt"
        )
        with open(temp_path, "w") as f:
            f.write("lock test")

        # Start a subprocess that holds the file open
        holder = subprocess.Popen(
            [
                sys.executable, "-c",
                f"f = open(r'{temp_path}', 'r'); "
                f"import time; time.sleep(30)"
            ]
        )

        try:
            import time
            time.sleep(1)  # Give the subprocess time to open the file

            result = _analyzer.analyze(temp_path)
            assert result.is_locked is True
            assert result.detection_method == "restart_manager"
            assert len(result.processes) >= 1

            # Verify structured process info
            for proc in result.processes:
                assert isinstance(proc, ProcessInfo)
                assert proc.pid > 0
                assert isinstance(proc.process_name, str)
        finally:
            holder.terminate()
            holder.wait()
            if os.path.exists(temp_path):
                os.unlink(temp_path)
