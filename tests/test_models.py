"""
Unit tests for the shared data models.

These tests verify the structure and defaults of ProcessInfo,
LockDetectionResult, and AnalyzerResult.  They are fully
cross-platform and run on macOS, Linux, and Windows.
"""

import pytest

from diagnoser.models import (
    AnalyzerResult,
    DiagnosisResult,
    DiagnosisType,
    FileAttributeResult,
    FileOperation,
    LockDetectionResult,
    PermissionCheckResult,
    ProcessInfo,
    SyncConflictResult,
)


class TestProcessInfo:
    """Tests for the ProcessInfo dataclass."""

    def test_creation_with_all_fields(self):
        info = ProcessInfo(
            process_name="notepad.exe",
            pid=1234,
            executable_path=r"C:\Windows\notepad.exe",
        )
        assert info.process_name == "notepad.exe"
        assert info.pid == 1234
        assert info.executable_path == r"C:\Windows\notepad.exe"

    def test_default_executable_path(self):
        info = ProcessInfo(process_name="python.exe", pid=42)
        assert info.executable_path == ""

    def test_repr_is_readable(self):
        info = ProcessInfo(process_name="test.exe", pid=100)
        text = repr(info)
        assert "test.exe" in text
        assert "100" in text


class TestLockDetectionResult:
    """Tests for the LockDetectionResult dataclass."""

    def test_defaults(self):
        result = LockDetectionResult(file_path="/some/file.txt")
        assert result.file_path == "/some/file.txt"
        assert result.is_locked is False
        assert result.processes == []
        assert result.error is None
        assert result.detection_method == ""

    def test_locked_result_with_processes(self):
        procs = [
            ProcessInfo(process_name="app1.exe", pid=10),
            ProcessInfo(process_name="app2.exe", pid=20),
        ]
        result = LockDetectionResult(
            file_path="/locked/file.txt",
            is_locked=True,
            processes=procs,
            detection_method="restart_manager",
        )
        assert result.is_locked is True
        assert len(result.processes) == 2
        assert result.processes[0].process_name == "app1.exe"
        assert result.detection_method == "restart_manager"

    def test_error_result(self):
        result = LockDetectionResult(
            file_path="/missing/file.txt",
            is_locked=False,
            error="File does not exist: /missing/file.txt",
            detection_method="error",
        )
        assert result.error is not None
        assert "does not exist" in result.error

    def test_processes_are_independent_across_instances(self):
        """Ensure the default mutable list is not shared between instances."""
        r1 = LockDetectionResult(file_path="a.txt")
        r2 = LockDetectionResult(file_path="b.txt")
        r1.processes.append(ProcessInfo(process_name="x.exe", pid=1))
        assert len(r2.processes) == 0


class TestAnalyzerResult:
    """Tests for the generic AnalyzerResult dataclass."""

    def test_defaults(self):
        result = AnalyzerResult()
        assert result.detected is False
        assert result.issue == ""
        assert result.details == ""
        assert result.severity == "none"
        assert result.evidence == []
        assert result.analyzer_name == ""

    def test_populated_result(self):
        result = AnalyzerResult(
            detected=True,
            issue="File is read-only",
            details="The read-only attribute is set on this file.",
            severity="warning",
            evidence=["attrib +R"],
            analyzer_name="FileAttributeAnalyzer",
        )
        assert result.detected is True
        assert result.severity == "warning"
        assert len(result.evidence) == 1


class TestPermissionCheckResult:
    """Tests for the PermissionCheckResult dataclass."""

    def test_defaults(self):
        result = PermissionCheckResult(file_path="/some/file.txt")
        assert result.file_path == "/some/file.txt"
        assert result.operation == ""
        assert result.permitted is False
        assert result.owner == ""
        assert result.current_user == ""
        assert result.details == ""
        assert result.permission_bits == {}
        assert result.error is None
        assert result.detection_method == ""

    def test_populated_result(self):
        result = PermissionCheckResult(
            file_path=r"C:\test.txt",
            operation="write",
            permitted=False,
            owner=r"BUILTIN\Administrators",
            current_user="testuser",
            details="WRITE access is DENIED for user 'testuser'.",
            permission_bits={"read": True, "write": False, "execute": False},
            detection_method="windows_acl",
        )
        assert result.permitted is False
        assert result.owner == r"BUILTIN\Administrators"
        assert result.permission_bits["read"] is True
        assert result.permission_bits["write"] is False
        assert result.detection_method == "windows_acl"

    def test_permission_bits_independent_across_instances(self):
        """Ensure the default mutable dict is not shared between instances."""
        r1 = PermissionCheckResult(file_path="a.txt")
        r2 = PermissionCheckResult(file_path="b.txt")
        r1.permission_bits["read"] = True
        assert "read" not in r2.permission_bits


class TestFileOperation:
    """Tests for the FileOperation enum."""

    def test_enum_values(self):
        assert FileOperation.READ.value == "read"
        assert FileOperation.WRITE.value == "write"
        assert FileOperation.EXECUTE.value == "execute"
        assert FileOperation.DELETE.value == "delete"

    def test_enum_membership(self):
        assert len(FileOperation) == 4


class TestDiagnosisType:
    """Tests for the DiagnosisType enum."""

    def test_enum_values(self):
        assert DiagnosisType.FILE_NOT_FOUND.value == "file_not_found"
        assert DiagnosisType.FILE_LOCKED.value == "file_locked"
        assert DiagnosisType.PERMISSION_DENIED.value == "permission_denied"
        assert DiagnosisType.READ_ONLY.value == "read_only"
        assert DiagnosisType.OPERATION_ALLOWED.value == "operation_allowed"
        assert DiagnosisType.UNKNOWN_ERROR.value == "unknown_error"
        assert DiagnosisType.SYNC_CONFLICT.value == "sync_conflict"

    def test_enum_membership(self):
        assert len(DiagnosisType) == 7


class TestDiagnosisResult:
    """Tests for the DiagnosisResult dataclass."""

    def test_defaults(self):
        result = DiagnosisResult(file_path="/some/file.txt")
        assert result.file_path == "/some/file.txt"
        assert result.operation == ""
        assert result.diagnosis == DiagnosisType.UNKNOWN_ERROR
        assert result.reason == ""
        assert result.suggested_action == ""
        assert result.lock_result is None
        assert result.permission_result is None
        assert result.attribute_result is None
        assert result.sync_result is None

    def test_populated_result(self):
        attr_res = FileAttributeResult(
            file_path=r"C:\test.txt",
            is_readonly=True,
            attributes_list=["READONLY"],
            detection_method="windows_stat",
        )
        sync_res = SyncConflictResult(
            file_path=r"C:\test.txt",
            is_synced=True,
            provider="onedrive",
            detection_method="local_sync_detection",
        )
        result = DiagnosisResult(
            file_path=r"C:\test.txt",
            operation="write",
            diagnosis=DiagnosisType.FILE_LOCKED,
            reason="File is currently locked by notepad.exe (PID 1234).",
            suggested_action="Close the process holding the file and retry.",
            lock_result=LockDetectionResult(
                file_path=r"C:\test.txt",
                is_locked=True,
                processes=[ProcessInfo(process_name="notepad.exe", pid=1234)],
                detection_method="restart_manager",
            ),
            attribute_result=attr_res,
            sync_result=sync_res,
        )
        assert result.diagnosis == DiagnosisType.FILE_LOCKED
        assert result.lock_result is not None
        assert result.lock_result.is_locked is True
        assert result.permission_result is None
        assert result.attribute_result is attr_res
        assert result.attribute_result.is_readonly is True
        assert result.sync_result is sync_res
        assert result.sync_result.provider == "onedrive"


class TestFileAttributeResult:
    """Tests for the FileAttributeResult dataclass."""

    def test_defaults(self):
        result = FileAttributeResult(file_path="/some/file.txt")
        assert result.file_path == "/some/file.txt"
        assert result.is_readonly is None
        assert result.is_hidden is None
        assert result.is_system is None
        assert result.is_archive is None
        assert result.is_reparse_point is None
        assert result.is_offline is None
        assert result.raw_attributes is None
        assert result.attributes_list == []
        assert result.error is None
        assert result.detection_method == ""

    def test_populated_result(self):
        result = FileAttributeResult(
            file_path=r"C:\test.txt",
            is_readonly=True,
            is_hidden=False,
            is_system=False,
            is_archive=True,
            is_reparse_point=False,
            is_offline=False,
            raw_attributes=0x21,
            attributes_list=["READONLY", "ARCHIVE"],
            detection_method="windows_stat",
        )
        assert result.is_readonly is True
        assert result.is_archive is True
        assert result.raw_attributes == 0x21
        assert "READONLY" in result.attributes_list
        assert result.detection_method == "windows_stat"

    def test_attributes_list_independent_across_instances(self):
        r1 = FileAttributeResult(file_path="a.txt")
        r2 = FileAttributeResult(file_path="b.txt")
        r1.attributes_list.append("READONLY")
        assert len(r2.attributes_list) == 0


class TestSyncConflictResult:
    """Tests for the SyncConflictResult dataclass."""

    def test_defaults(self):
        result = SyncConflictResult(file_path="/some/file.txt")
        assert result.file_path == "/some/file.txt"
        assert result.is_synced is None
        assert result.provider == ""
        assert result.sync_root == ""
        assert result.client_running is False
        assert result.evidence_level == "none"
        assert result.is_conflict is False
        assert result.locking_process is None
        assert result.details == ""
        assert result.error is None
        assert result.detection_method == ""

    def test_populated_result(self):
        proc = ProcessInfo(process_name="OneDrive.exe", pid=9876)
        result = SyncConflictResult(
            file_path=r"C:\Users\test\OneDrive\doc.txt",
            is_synced=True,
            provider="onedrive",
            sync_root=r"C:\Users\test\OneDrive",
            client_running=True,
            evidence_level="confirmed_lock",
            is_conflict=True,
            locking_process=proc,
            details="OneDrive holds an active file lock.",
            detection_method="local_sync_detection",
        )
        assert result.is_synced is True
        assert result.provider == "onedrive"
        assert result.client_running is True
        assert result.is_conflict is True
        assert result.locking_process is not None
        assert result.locking_process.pid == 9876
        assert result.evidence_level == "confirmed_lock"
