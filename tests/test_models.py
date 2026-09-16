"""
Unit tests for the shared data models.

These tests verify the structure and defaults of ProcessInfo,
LockDetectionResult, and AnalyzerResult.  They are fully
cross-platform and run on macOS, Linux, and Windows.
"""

import pytest

from diagnoser.models import AnalyzerResult, LockDetectionResult, ProcessInfo


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
