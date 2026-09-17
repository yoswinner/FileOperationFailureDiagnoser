"""
Unit tests for the DiagnosisEngine.

Tests are divided into groups:

1. Cross-platform tests (run on macOS/Linux/Windows):
   - Nonexistent file → FILE_NOT_FOUND
   - Existing readable file + READ → OPERATION_ALLOWED
   - Existing writable file + WRITE → OPERATION_ALLOWED
   - Existing writable file + DELETE → OPERATION_ALLOWED
   - Read-only file + WRITE → READ_ONLY
   - Read-only file + DELETE → READ_ONLY
   - Result structure validation (file_path, operation, reason, etc.)
   - Default operation is READ
   - Path normalisation
   - Locked file → FILE_LOCKED (via mock)
   - Lock reason includes process information
   - Suggested action is populated

2. Windows-only tests (skipped on non-Windows):
   - Real lock detection via Restart Manager integration

All tests use DiagnosisResult structured output — the engine
never prints directly to the console.

Tests do NOT depend on a specific username, PID, temporary
filename, or machine-specific path.
"""

import os
import stat
import sys
import tempfile
from unittest.mock import MagicMock

import pytest

from diagnoser.engine.diagnosis import DiagnosisEngine
from diagnoser.models import (
    DiagnosisResult,
    DiagnosisType,
    FileOperation,
    LockDetectionResult,
    PermissionCheckResult,
    ProcessInfo,
)


# ======================================================================
# Cross-platform tests
# ======================================================================

class TestDiagnosisEngineCrossPlatform:
    """Tests that run on any platform."""

    # ------------------------------------------------------------------
    # FILE_NOT_FOUND
    # ------------------------------------------------------------------

    def test_nonexistent_file_returns_file_not_found(self):
        """A file that does not exist → FILE_NOT_FOUND."""
        engine = DiagnosisEngine()
        result = engine.diagnose(
            "/nonexistent/path/to/file.txt", FileOperation.READ,
        )
        assert isinstance(result, DiagnosisResult)
        assert result.diagnosis == DiagnosisType.FILE_NOT_FOUND
        assert result.reason != ""
        assert "does not exist" in result.reason

    def test_file_not_found_has_suggested_action(self):
        """FILE_NOT_FOUND should include a suggested action."""
        engine = DiagnosisEngine()
        result = engine.diagnose(
            "/nonexistent/file.txt", FileOperation.WRITE,
        )
        assert result.suggested_action != ""

    def test_file_not_found_contains_file_path(self):
        """The result should contain the normalised file path."""
        engine = DiagnosisEngine()
        result = engine.diagnose(
            "/nonexistent/file.txt", FileOperation.READ,
        )
        assert os.path.isabs(result.file_path)

    def test_file_not_found_contains_operation(self):
        """The result should contain the requested operation."""
        engine = DiagnosisEngine()
        result = engine.diagnose(
            "/nonexistent/file.txt", FileOperation.WRITE,
        )
        assert result.operation == "write"

    def test_file_not_found_no_lock_or_perm_results(self):
        """FILE_NOT_FOUND skips lock and permission checks."""
        engine = DiagnosisEngine()
        result = engine.diagnose(
            "/nonexistent/file.txt", FileOperation.READ,
        )
        assert result.lock_result is None
        assert result.permission_result is None

    # ------------------------------------------------------------------
    # OPERATION_ALLOWED
    # ------------------------------------------------------------------

    def test_readable_file_read_allowed(self):
        """Existing readable file + READ → OPERATION_ALLOWED."""
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".txt"
        ) as f:
            temp_path = f.name
            f.write(b"test content")

        try:
            engine = DiagnosisEngine()
            result = engine.diagnose(temp_path, FileOperation.READ)
            assert result.diagnosis == DiagnosisType.OPERATION_ALLOWED
            assert result.reason != ""
        finally:
            os.unlink(temp_path)

    def test_writable_file_write_allowed(self):
        """Existing writable file + WRITE → OPERATION_ALLOWED."""
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".txt"
        ) as f:
            temp_path = f.name
            f.write(b"test content")

        try:
            engine = DiagnosisEngine()
            result = engine.diagnose(temp_path, FileOperation.WRITE)
            assert result.diagnosis == DiagnosisType.OPERATION_ALLOWED
        finally:
            os.unlink(temp_path)

    def test_writable_file_delete_allowed(self):
        """Existing writable file + DELETE → OPERATION_ALLOWED."""
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".txt"
        ) as f:
            temp_path = f.name
            f.write(b"test content")

        try:
            engine = DiagnosisEngine()
            result = engine.diagnose(temp_path, FileOperation.DELETE)
            assert result.diagnosis == DiagnosisType.OPERATION_ALLOWED
        finally:
            os.unlink(temp_path)

    def test_allowed_includes_lock_and_perm_results(self):
        """OPERATION_ALLOWED should carry the raw sub-results."""
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".txt"
        ) as f:
            temp_path = f.name

        try:
            engine = DiagnosisEngine()
            result = engine.diagnose(temp_path, FileOperation.READ)
            assert result.lock_result is not None
            assert result.permission_result is not None
        finally:
            os.unlink(temp_path)

    def test_allowed_has_empty_suggested_action(self):
        """OPERATION_ALLOWED needs no corrective action."""
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".txt"
        ) as f:
            temp_path = f.name

        try:
            engine = DiagnosisEngine()
            result = engine.diagnose(temp_path, FileOperation.READ)
            assert result.suggested_action == ""
        finally:
            os.unlink(temp_path)

    def test_default_operation_is_read(self):
        """If no operation is specified, default to READ."""
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".txt"
        ) as f:
            temp_path = f.name

        try:
            engine = DiagnosisEngine()
            result = engine.diagnose(temp_path)
            assert result.operation == "read"
        finally:
            os.unlink(temp_path)

    # ------------------------------------------------------------------
    # PERMISSION_DENIED / READ_ONLY
    # ------------------------------------------------------------------

    def test_readonly_file_write_denied(self):
        """A read-only file + WRITE → READ_ONLY."""
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".txt"
        ) as f:
            temp_path = f.name
            f.write(b"read-only content")

        try:
            os.chmod(
                temp_path,
                stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH,
            )
            engine = DiagnosisEngine()
            result = engine.diagnose(temp_path, FileOperation.WRITE)
            assert result.diagnosis == DiagnosisType.READ_ONLY
            assert "read-only" in result.reason.lower()
            assert result.suggested_action != ""
        finally:
            os.chmod(temp_path, stat.S_IRUSR | stat.S_IWUSR)
            os.unlink(temp_path)

    def test_readonly_file_delete_denied(self):
        """A read-only file + DELETE → READ_ONLY."""
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".txt"
        ) as f:
            temp_path = f.name
            f.write(b"read-only content")

        try:
            os.chmod(
                temp_path,
                stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH,
            )
            engine = DiagnosisEngine()
            result = engine.diagnose(temp_path, FileOperation.DELETE)
            assert result.diagnosis == DiagnosisType.READ_ONLY
        finally:
            os.chmod(temp_path, stat.S_IRUSR | stat.S_IWUSR)
            os.unlink(temp_path)

    def test_permission_denied_has_perm_result(self):
        """Permission failure should carry the raw PermissionCheckResult."""
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".txt"
        ) as f:
            temp_path = f.name

        try:
            os.chmod(
                temp_path,
                stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH,
            )
            engine = DiagnosisEngine()
            result = engine.diagnose(temp_path, FileOperation.WRITE)
            assert result.permission_result is not None
            assert isinstance(
                result.permission_result, PermissionCheckResult,
            )
        finally:
            os.chmod(temp_path, stat.S_IRUSR | stat.S_IWUSR)
            os.unlink(temp_path)

    def test_permission_denied_has_suggested_action(self):
        """Permission failure should include a suggested action."""
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".txt"
        ) as f:
            temp_path = f.name

        try:
            os.chmod(
                temp_path,
                stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH,
            )
            engine = DiagnosisEngine()
            result = engine.diagnose(temp_path, FileOperation.WRITE)
            assert result.suggested_action != ""
        finally:
            os.chmod(temp_path, stat.S_IRUSR | stat.S_IWUSR)
            os.unlink(temp_path)

    # ------------------------------------------------------------------
    # FILE_LOCKED (via mock — no Windows dependency)
    # ------------------------------------------------------------------

    def test_locked_file_returns_file_locked(self):
        """When the lock analyzer reports locked → FILE_LOCKED."""
        mock_lock = MagicMock()
        mock_lock.analyze.return_value = LockDetectionResult(
            file_path="/tmp/test.txt",
            is_locked=True,
            processes=[
                ProcessInfo(process_name="editor.exe", pid=9999),
            ],
            detection_method="restart_manager",
        )

        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".txt"
        ) as f:
            temp_path = f.name

        try:
            # Override just the lock analyzer return value
            mock_lock.analyze.return_value = LockDetectionResult(
                file_path=temp_path,
                is_locked=True,
                processes=[
                    ProcessInfo(process_name="editor.exe", pid=9999),
                ],
                detection_method="restart_manager",
            )
            engine = DiagnosisEngine(lock_analyzer=mock_lock)
            result = engine.diagnose(temp_path, FileOperation.WRITE)
            assert result.diagnosis == DiagnosisType.FILE_LOCKED
        finally:
            os.unlink(temp_path)

    def test_locked_reason_contains_process_info(self):
        """FILE_LOCKED reason should mention the locking process."""
        mock_lock = MagicMock()

        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".txt"
        ) as f:
            temp_path = f.name

        try:
            mock_lock.analyze.return_value = LockDetectionResult(
                file_path=temp_path,
                is_locked=True,
                processes=[
                    ProcessInfo(
                        process_name="notepad.exe",
                        pid=1234,
                        executable_path=r"C:\Windows\notepad.exe",
                    ),
                ],
                detection_method="restart_manager",
            )
            engine = DiagnosisEngine(lock_analyzer=mock_lock)
            result = engine.diagnose(temp_path, FileOperation.WRITE)
            assert "notepad.exe" in result.reason
            assert "1234" in result.reason
        finally:
            os.unlink(temp_path)

    def test_locked_has_suggested_action(self):
        """FILE_LOCKED should include a suggested action."""
        mock_lock = MagicMock()

        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".txt"
        ) as f:
            temp_path = f.name

        try:
            mock_lock.analyze.return_value = LockDetectionResult(
                file_path=temp_path,
                is_locked=True,
                processes=[
                    ProcessInfo(process_name="app.exe", pid=42),
                ],
                detection_method="restart_manager",
            )
            engine = DiagnosisEngine(lock_analyzer=mock_lock)
            result = engine.diagnose(temp_path, FileOperation.WRITE)
            assert result.suggested_action != ""
            assert "close" in result.suggested_action.lower()
        finally:
            os.unlink(temp_path)

    def test_locked_carries_lock_result(self):
        """FILE_LOCKED should carry the raw LockDetectionResult."""
        mock_lock = MagicMock()

        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".txt"
        ) as f:
            temp_path = f.name

        try:
            lock_data = LockDetectionResult(
                file_path=temp_path,
                is_locked=True,
                processes=[
                    ProcessInfo(process_name="app.exe", pid=42),
                ],
                detection_method="restart_manager",
            )
            mock_lock.analyze.return_value = lock_data
            engine = DiagnosisEngine(lock_analyzer=mock_lock)
            result = engine.diagnose(temp_path, FileOperation.READ)
            assert result.lock_result is lock_data
            assert result.lock_result.processes[0].pid == 42
        finally:
            os.unlink(temp_path)

    def test_locked_without_process_info(self):
        """FILE_LOCKED with no process list still produces a reason."""
        mock_lock = MagicMock()

        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".txt"
        ) as f:
            temp_path = f.name

        try:
            mock_lock.analyze.return_value = LockDetectionResult(
                file_path=temp_path,
                is_locked=True,
                processes=[],
                detection_method="restart_manager",
            )
            engine = DiagnosisEngine(lock_analyzer=mock_lock)
            result = engine.diagnose(temp_path, FileOperation.WRITE)
            assert result.diagnosis == DiagnosisType.FILE_LOCKED
            assert result.reason != ""
        finally:
            os.unlink(temp_path)

    def test_locked_with_multiple_processes(self):
        """FILE_LOCKED with multiple lockers mentions all of them."""
        mock_lock = MagicMock()

        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".txt"
        ) as f:
            temp_path = f.name

        try:
            mock_lock.analyze.return_value = LockDetectionResult(
                file_path=temp_path,
                is_locked=True,
                processes=[
                    ProcessInfo(process_name="app1.exe", pid=100),
                    ProcessInfo(process_name="app2.exe", pid=200),
                ],
                detection_method="restart_manager",
            )
            engine = DiagnosisEngine(lock_analyzer=mock_lock)
            result = engine.diagnose(temp_path, FileOperation.WRITE)
            assert "app1.exe" in result.reason
            assert "app2.exe" in result.reason
        finally:
            os.unlink(temp_path)

    # ------------------------------------------------------------------
    # Priority order: lock is checked before permission
    # ------------------------------------------------------------------

    def test_lock_takes_priority_over_permission(self):
        """A locked read-only file → FILE_LOCKED (not READ_ONLY)."""
        mock_lock = MagicMock()

        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".txt"
        ) as f:
            temp_path = f.name

        try:
            os.chmod(
                temp_path,
                stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH,
            )
            mock_lock.analyze.return_value = LockDetectionResult(
                file_path=temp_path,
                is_locked=True,
                processes=[
                    ProcessInfo(process_name="app.exe", pid=1),
                ],
                detection_method="restart_manager",
            )
            engine = DiagnosisEngine(lock_analyzer=mock_lock)
            result = engine.diagnose(temp_path, FileOperation.WRITE)
            # Lock should take priority
            assert result.diagnosis == DiagnosisType.FILE_LOCKED
        finally:
            os.chmod(temp_path, stat.S_IRUSR | stat.S_IWUSR)
            os.unlink(temp_path)

    # ------------------------------------------------------------------
    # Result structure
    # ------------------------------------------------------------------

    def test_result_has_all_fields(self):
        """DiagnosisResult should have all expected attributes."""
        engine = DiagnosisEngine()
        result = engine.diagnose(
            "/nonexistent/file.txt", FileOperation.READ,
        )
        assert hasattr(result, "file_path")
        assert hasattr(result, "operation")
        assert hasattr(result, "diagnosis")
        assert hasattr(result, "reason")
        assert hasattr(result, "suggested_action")
        assert hasattr(result, "lock_result")
        assert hasattr(result, "permission_result")

    def test_path_is_normalised(self):
        """The file_path in the result should be absolute and normalised."""
        engine = DiagnosisEngine()
        result = engine.diagnose(
            "./relative/../relative/file.txt", FileOperation.READ,
        )
        assert os.path.isabs(result.file_path)
        assert ".." not in result.file_path

    def test_all_operations_accepted(self):
        """All FileOperation enum values should work without error."""
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".txt"
        ) as f:
            temp_path = f.name

        try:
            engine = DiagnosisEngine()
            for op in FileOperation:
                result = engine.diagnose(temp_path, op)
                assert isinstance(result, DiagnosisResult)
                assert result.operation == op.value
        finally:
            os.unlink(temp_path)


# ======================================================================
# Windows-only tests
# ======================================================================

@pytest.mark.skipif(
    sys.platform != "win32",
    reason="Requires Windows Restart Manager API"
)
class TestDiagnosisEngineWindows:
    """Integration tests using the real lock analyzer on Windows."""

    def test_unlocked_file_write_allowed(self):
        """An unlocked writable file on Windows → OPERATION_ALLOWED."""
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".txt"
        ) as f:
            temp_path = f.name
            f.write(b"windows test")

        try:
            engine = DiagnosisEngine()
            result = engine.diagnose(temp_path, FileOperation.WRITE)
            assert result.diagnosis == DiagnosisType.OPERATION_ALLOWED
            # On Windows, lock_result should use restart_manager
            assert result.lock_result is not None
            assert result.lock_result.detection_method == "restart_manager"
        finally:
            os.unlink(temp_path)

    def test_locked_file_detected_windows(self):
        """A file locked by a subprocess on Windows → FILE_LOCKED."""
        import subprocess
        import time

        temp_path = os.path.join(
            tempfile.gettempdir(), "diagnoser_engine_lock_test.txt",
        )
        with open(temp_path, "w") as f:
            f.write("lock test")

        holder = subprocess.Popen(
            [
                sys.executable, "-c",
                f"f = open(r'{temp_path}', 'r'); "
                f"import time; time.sleep(30)"
            ]
        )

        try:
            time.sleep(1)

            engine = DiagnosisEngine()
            result = engine.diagnose(temp_path, FileOperation.WRITE)
            assert result.diagnosis == DiagnosisType.FILE_LOCKED
            assert result.lock_result is not None
            assert len(result.lock_result.processes) >= 1
        finally:
            holder.kill()
            try:
                holder.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass

            for _attempt in range(5):
                try:
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)
                    break
                except PermissionError:
                    time.sleep(0.5)
