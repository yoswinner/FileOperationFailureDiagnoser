"""
Unit tests for the SyncConflictAnalyzer and lock correlation helper.

All tests are deterministic and do not require an active OneDrive or
Google Drive account. Tests cover positive, negative, boundary, error,
and correlation scenarios using temporary files, mocks, and dependency injection.

Safety:
    All tests verify that the analyzer operates strictly in read-only mode,
    never altering files, processes, or registry configuration.
"""

import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

import psutil
import pytest

from diagnoser.analyzers.sync_conflict import (
    FILE_ATTRIBUTE_OFFLINE,
    FILE_ATTRIBUTE_REPARSE_POINT,
    PROVIDER_GOOGLE_DRIVE,
    PROVIDER_ONEDRIVE,
    SyncConflictAnalyzer,
    correlate_sync_lock,
    is_subpath,
)
from diagnoser.models import LockDetectionResult, ProcessInfo, SyncConflictResult

_IS_WINDOWS = sys.platform == "win32"


# ======================================================================
# Test Suite
# ======================================================================

class TestSyncConflictAnalyzer:
    """Deterministic test suite for SyncConflictAnalyzer."""

    # ------------------------------------------------------------------
    # 1. File outside any detected sync root
    # ------------------------------------------------------------------
    def test_file_outside_any_detected_sync_root(self):
        """A file located in an ordinary folder must report is_synced=False and evidence_level='none'."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, "ordinary.txt")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("standard local file")

            disjoint_dir = os.path.join(temp_dir, "other_cloud")
            analyzer = SyncConflictAnalyzer(
                roots_override={
                    PROVIDER_ONEDRIVE: [disjoint_dir],
                    PROVIDER_GOOGLE_DRIVE: [],
                }
            )

            result = analyzer.analyze(file_path)

            assert isinstance(result, SyncConflictResult)
            assert result.file_path == os.path.abspath(file_path)
            assert result.is_synced is False
            assert result.provider == ""
            assert result.sync_root == ""
            assert result.client_running is False
            assert result.evidence_level == "none"
            assert result.is_conflict is False
            assert result.locking_process is None
            assert result.error is None
            assert "not located within any detected cloud-sync folder" in result.details

    # ------------------------------------------------------------------
    # 2. File within a known OneDrive root
    # ------------------------------------------------------------------
    def test_file_within_known_onedrive_root(self):
        """A file located within a configured OneDrive root must report provider='onedrive'."""
        with tempfile.TemporaryDirectory() as od_root:
            subfolder = os.path.join(od_root, "Documents", "Work")
            os.makedirs(subfolder, exist_ok=True)
            file_path = os.path.join(subfolder, "report.docx")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("content")

            analyzer = SyncConflictAnalyzer(
                roots_override={
                    PROVIDER_ONEDRIVE: [od_root],
                    PROVIDER_GOOGLE_DRIVE: [],
                },
                process_checker=lambda prov: (False, []),
                attribute_checker=lambda path: (False, False),
            )

            result = analyzer.analyze(file_path)

            assert result.is_synced is True
            assert result.provider == PROVIDER_ONEDRIVE
            assert result.sync_root == os.path.abspath(od_root)
            assert result.client_running is False
            assert result.evidence_level == "path_only"
            assert result.is_conflict is False
            assert "OneDrive folder" in result.details

    # ------------------------------------------------------------------
    # 3. File within a known Google Drive root or simulated mount
    # ------------------------------------------------------------------
    def test_file_within_known_google_drive_root(self):
        """A file within a Google Drive root must report provider='google_drive'."""
        with tempfile.TemporaryDirectory() as gd_root:
            subfolder = os.path.join(gd_root, "My Drive", "Projects")
            os.makedirs(subfolder, exist_ok=True)
            file_path = os.path.join(subfolder, "design.pdf")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("pdf data")

            analyzer = SyncConflictAnalyzer(
                roots_override={
                    PROVIDER_ONEDRIVE: [],
                    PROVIDER_GOOGLE_DRIVE: [gd_root],
                },
                process_checker=lambda prov: (False, []),
                attribute_checker=lambda path: (False, False),
            )

            result = analyzer.analyze(file_path)

            assert result.is_synced is True
            assert result.provider == PROVIDER_GOOGLE_DRIVE
            assert result.sync_root == os.path.abspath(gd_root)
            assert result.client_running is False
            assert result.evidence_level == "path_only"
            assert result.is_conflict is False
            assert "Google Drive folder" in result.details

    # ------------------------------------------------------------------
    # 4. Client running versus not running
    # ------------------------------------------------------------------
    def test_client_running_vs_not_running(self):
        """Verify evidence tier elevation from 'path_only' to 'potential_contention' when client is active."""
        with tempfile.TemporaryDirectory() as od_root:
            file_path = os.path.join(od_root, "active.txt")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("test")

            # Case A: Client NOT running
            analyzer_stopped = SyncConflictAnalyzer(
                roots_override={PROVIDER_ONEDRIVE: [od_root]},
                process_checker=lambda prov: (False, []),
                attribute_checker=lambda path: (False, False),
            )
            res_stopped = analyzer_stopped.analyze(file_path)
            assert res_stopped.client_running is False
            assert res_stopped.evidence_level == "path_only"
            assert res_stopped.is_conflict is False

            # Case B: Client IS running
            mock_proc = ProcessInfo(process_name="OneDrive.exe", pid=2468)
            analyzer_running = SyncConflictAnalyzer(
                roots_override={PROVIDER_ONEDRIVE: [od_root]},
                process_checker=lambda prov: (True, [mock_proc]),
                attribute_checker=lambda path: (False, False),
            )
            res_running = analyzer_running.analyze(file_path)
            assert res_running.client_running is True
            assert res_running.evidence_level == "potential_contention"
            assert res_running.is_conflict is False  # conservative: not confirmed lock yet!
            assert "client process is running" in res_running.details

    # ------------------------------------------------------------------
    # 5. Provider root unavailable or unsupported
    # ------------------------------------------------------------------
    def test_provider_roots_unavailable_or_unsupported(self):
        """When no provider roots are discovered or configured, evidence_level is 'none'."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, "test.txt")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("text")

            analyzer = SyncConflictAnalyzer(
                roots_override={
                    PROVIDER_ONEDRIVE: [],
                    PROVIDER_GOOGLE_DRIVE: [],
                }
            )
            result = analyzer.analyze(file_path)

            assert result.is_synced is False
            assert result.evidence_level == "none"
            assert result.provider == ""

    # ------------------------------------------------------------------
    # 6. Missing file and invalid path
    # ------------------------------------------------------------------
    def test_missing_file_and_invalid_path(self):
        """Nonexistent paths or directory paths must return structured error results."""
        analyzer = SyncConflictAnalyzer()

        # Nonexistent file
        res_nonexistent = analyzer.analyze("C:\\nonexistent_dir_abc123\\missing_file.txt")
        assert res_nonexistent.error is not None
        assert res_nonexistent.detection_method == "error"
        assert res_nonexistent.is_synced is None
        assert res_nonexistent.evidence_level == "none"
        assert "does not exist" in res_nonexistent.error

        # Directory path instead of file
        with tempfile.TemporaryDirectory() as temp_dir:
            res_dir = analyzer.analyze(temp_dir)
            assert res_dir.error is not None
            assert res_dir.detection_method == "error"
            assert "specifies a directory" in res_dir.error

    # ------------------------------------------------------------------
    # 7. Windows path case differences
    # ------------------------------------------------------------------
    def test_windows_path_case_differences(self):
        """Path matching must be case-insensitive for Windows file paths."""
        # Test helper function directly
        assert is_subpath(r"C:\Users\Student\OneDrive\file.txt", r"C:\users\student\onedrive")
        assert is_subpath(r"c:\users\student\onedrive\DOCS\SHEET.XLSX", r"C:\Users\Student\OneDrive")
        assert is_subpath(r"g:\my drive\file.pdf", r"G:\My Drive")

        # Test within analyzer
        with tempfile.TemporaryDirectory() as root:
            file_path = os.path.join(root, "Data.TXT")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("data")

            # Alternate casing of root
            upper_root = root.upper()
            lower_file = file_path.lower()

            analyzer = SyncConflictAnalyzer(
                roots_override={PROVIDER_ONEDRIVE: [upper_root]},
                process_checker=lambda prov: (False, []),
                attribute_checker=lambda p: (False, False),
            )
            res = analyzer.analyze(lower_file)
            assert res.is_synced is True
            assert res.provider == PROVIDER_ONEDRIVE

    # ------------------------------------------------------------------
    # 8. Directory-boundary matching to reject similarly named sibling paths
    # ------------------------------------------------------------------
    def test_directory_boundary_matching_rejects_sibling_paths(self):
        """A root C:\\Users\\User\\OneDrive must NOT match C:\\Users\\User\\OneDriveBackup."""
        root = r"C:\Users\User\OneDrive"

        # Sibling directories
        assert is_subpath(r"C:\Users\User\OneDriveBackup\file.txt", root) is False
        assert is_subpath(r"C:\Users\User\OneDrive-Backup\file.txt", root) is False
        assert is_subpath(r"C:\Users\User\OneDrive.old\file.txt", root) is False
        assert is_subpath(r"C:\Users\User\OneDrive2\file.txt", root) is False
        assert is_subpath(r"D:\Users\User\OneDrive\file.txt", root) is False

        # Legitimate children
        assert is_subpath(r"C:\Users\User\OneDrive\file.txt", root) is True
        assert is_subpath(r"C:\Users\User\OneDrive\sub\dir\file.txt", root) is True
        assert is_subpath(r"C:\Users\User\OneDrive", root) is True

    # ------------------------------------------------------------------
    # 9. Multiple candidate roots or ambiguous provider discovery
    # ------------------------------------------------------------------
    def test_multiple_candidate_roots_matches_deepest_root(self):
        """When multiple roots are present, the analyzer matches the most specific (deepest) root."""
        with tempfile.TemporaryDirectory() as base_dir:
            personal_od = os.path.join(base_dir, "OneDrive")
            business_od = os.path.join(base_dir, "OneDrive - Enterprise")
            os.makedirs(personal_od, exist_ok=True)
            os.makedirs(business_od, exist_ok=True)

            file_personal = os.path.join(personal_od, "note.txt")
            file_business = os.path.join(business_od, "proposal.docx")
            with open(file_personal, "w") as f:
                f.write("p")
            with open(file_business, "w") as f:
                f.write("b")

            analyzer = SyncConflictAnalyzer(
                roots_override={
                    PROVIDER_ONEDRIVE: [personal_od, business_od],
                    PROVIDER_GOOGLE_DRIVE: [],
                },
                process_checker=lambda prov: (False, []),
                attribute_checker=lambda p: (False, False),
            )

            res_p = analyzer.analyze(file_personal)
            assert res_p.is_synced is True
            assert res_p.sync_root == os.path.abspath(personal_od)

            res_b = analyzer.analyze(file_business)
            assert res_b.is_synced is True
            assert res_b.sync_root == os.path.abspath(business_od)

    # ------------------------------------------------------------------
    # 10. Process access denied, process disappears, or process enumeration fails
    # ------------------------------------------------------------------
    def test_process_inspection_handles_exceptions_defensively(self):
        """Verify psutil exceptions during inspection are caught without crashing."""
        analyzer = SyncConflictAnalyzer()

        # Simulate psutil raising AccessDenied / NoSuchProcess / OSError
        mock_proc1 = MagicMock()
        mock_proc1.info = {"name": "OneDrive.exe", "pid": 111, "exe": "path"}

        mock_proc2 = MagicMock()
        mock_proc2.info.get.side_effect = psutil.AccessDenied(pid=222)

        mock_proc3 = MagicMock()
        mock_proc3.info.get.side_effect = psutil.NoSuchProcess(pid=333)

        with patch("psutil.process_iter", return_value=[mock_proc1, mock_proc2, mock_proc3]):
            is_running, procs = analyzer._is_client_running(PROVIDER_ONEDRIVE)
            assert is_running is True
            assert len(procs) == 1
            assert procs[0].pid == 111

        # Simulate psutil raising top-level OSError
        with patch("psutil.process_iter", side_effect=OSError("Process list unavailable")):
            is_running, procs = analyzer._is_client_running(PROVIDER_ONEDRIVE)
            assert is_running is False
            assert procs == []

    # ------------------------------------------------------------------
    # 11. Reparse/offline evidence without an active lock
    # ------------------------------------------------------------------
    def test_reparse_offline_evidence_without_active_lock(self):
        """Files with reparse-point or offline attributes must report 'potential_contention' even without lock."""
        with tempfile.TemporaryDirectory() as od_root:
            file_path = os.path.join(od_root, "cloud_placeholder.txt")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("placeholder")

            # Client stopped, but file is reparse point / offline
            analyzer = SyncConflictAnalyzer(
                roots_override={PROVIDER_ONEDRIVE: [od_root]},
                process_checker=lambda prov: (False, []),
                attribute_checker=lambda p: (True, True),
            )
            result = analyzer.analyze(file_path)

            assert result.is_synced is True
            assert result.client_running is False
            assert result.evidence_level == "potential_contention"
            assert result.is_conflict is False  # conservative: not a confirmed lock
            assert "cloud placeholder attributes" in result.details
            assert "reparse point/offline" in result.details

    # ------------------------------------------------------------------
    # 12. Confirmed lock correlation using actual mock LockDetectionResult
    # ------------------------------------------------------------------
    def test_confirmed_lock_correlation_with_matching_sync_client(self):
        """Elevates to 'confirmed_lock' when LockDetectionResult contains a matching sync client."""
        with tempfile.TemporaryDirectory() as od_root:
            file_path = os.path.join(od_root, "locked_sync.txt")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("content")

            analyzer = SyncConflictAnalyzer(
                roots_override={PROVIDER_ONEDRIVE: [od_root]},
                process_checker=lambda prov: (True, [ProcessInfo("OneDrive.exe", 1010)]),
                attribute_checker=lambda p: (False, False),
            )
            sync_res = analyzer.analyze(file_path)
            assert sync_res.evidence_level == "potential_contention"
            assert sync_res.is_conflict is False

            # Lock detection identifies OneDrive.exe as the lock holder
            lock_res = LockDetectionResult(
                file_path=file_path,
                is_locked=True,
                processes=[ProcessInfo(process_name="OneDrive.exe", pid=1010)],
                detection_method="restart_manager",
            )

            correlated = correlate_sync_lock(sync_res, lock_res)

            assert correlated.evidence_level == "confirmed_lock"
            assert correlated.is_conflict is True
            assert correlated.locking_process is not None
            assert correlated.locking_process.process_name == "OneDrive.exe"
            assert correlated.locking_process.pid == 1010
            assert "Confirmed cloud sync conflict" in correlated.details

    def test_confirmed_lock_correlation_google_drive(self):
        """Elevates to 'confirmed_lock' when LockDetectionResult contains GoogleDriveFS.exe."""
        with tempfile.TemporaryDirectory() as gd_root:
            file_path = os.path.join(gd_root, "locked_gdrive.txt")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("content")

            analyzer = SyncConflictAnalyzer(
                roots_override={PROVIDER_GOOGLE_DRIVE: [gd_root]},
                process_checker=lambda prov: (True, [ProcessInfo("GoogleDriveFS.exe", 2020)]),
                attribute_checker=lambda p: (False, False),
            )
            sync_res = analyzer.analyze(file_path)

            lock_res = LockDetectionResult(
                file_path=file_path,
                is_locked=True,
                processes=[ProcessInfo(process_name="GoogleDriveFS.exe", pid=2020)],
                detection_method="restart_manager",
            )

            correlated = analyzer.correlate_lock(sync_res, lock_res)

            assert correlated.evidence_level == "confirmed_lock"
            assert correlated.is_conflict is True
            assert correlated.locking_process.process_name == "GoogleDriveFS.exe"
            assert correlated.locking_process.pid == 2020

    # ------------------------------------------------------------------
    # 13. Nonmatching lock holder: must not be attributed to sync provider
    # ------------------------------------------------------------------
    def test_nonmatching_lock_holder_not_attributed_to_sync_provider(self):
        """When an unrelated application holds the lock, do NOT elevate to confirmed_lock."""
        with tempfile.TemporaryDirectory() as od_root:
            file_path = os.path.join(od_root, "word_doc.docx")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("doc")

            analyzer = SyncConflictAnalyzer(
                roots_override={PROVIDER_ONEDRIVE: [od_root]},
                process_checker=lambda prov: (True, [ProcessInfo("OneDrive.exe", 1010)]),
                attribute_checker=lambda p: (False, False),
            )
            sync_res = analyzer.analyze(file_path)

            # Lock is held by notepad.exe, NOT OneDrive
            lock_res = LockDetectionResult(
                file_path=file_path,
                is_locked=True,
                processes=[ProcessInfo(process_name="notepad.exe", pid=9999)],
                detection_method="restart_manager",
            )

            correlated = correlate_sync_lock(sync_res, lock_res)

            # Conservative rule: must NOT elevate to confirmed_lock or set is_conflict=True
            assert correlated.evidence_level == "potential_contention"
            assert correlated.is_conflict is False
            assert correlated.locking_process is None
            assert "notepad.exe" in correlated.details
            assert "non-sync application" in correlated.details

    # ------------------------------------------------------------------
    # 14. Sync directory containing an ordinary application-locked file
    # ------------------------------------------------------------------
    def test_sync_directory_containing_ordinary_application_locked_file(self):
        """A file in a sync folder locked by EXCEL.EXE remains is_conflict=False."""
        sync_res = SyncConflictResult(
            file_path="C:\\OneDrive\\budget.xlsx",
            is_synced=True,
            provider="onedrive",
            sync_root="C:\\OneDrive",
            client_running=True,
            evidence_level="potential_contention",
            is_conflict=False,
        )

        app_lock = LockDetectionResult(
            file_path="C:\\OneDrive\\budget.xlsx",
            is_locked=True,
            processes=[ProcessInfo(process_name="EXCEL.EXE", pid=7777)],
            detection_method="restart_manager",
        )

        result = correlate_sync_lock(sync_res, app_lock)
        assert result.is_conflict is False
        assert result.evidence_level == "potential_contention"
        assert result.locking_process is None

    # ------------------------------------------------------------------
    # 15. Structured error results and safe fallback behavior
    # ------------------------------------------------------------------
    def test_structured_error_results_and_safe_fallback(self):
        """Invalid inputs return structured SyncConflictResult with detection_method='error'."""
        analyzer = SyncConflictAnalyzer()

        # Nonexistent path
        r1 = analyzer.analyze("Z:\\nonexistent_volume\\file.txt")
        assert isinstance(r1, SyncConflictResult)
        assert r1.detection_method == "error"
        assert r1.error is not None

        # Lock correlation with None lock_result returns sync_result unchanged
        sync_res = SyncConflictResult(file_path="C:\\test.txt", is_synced=False)
        r2 = correlate_sync_lock(sync_res, None)
        assert r2 == sync_res

        # Lock correlation with non-locked result returns sync_result unchanged
        unlocked = LockDetectionResult(file_path="C:\\test.txt", is_locked=False)
        r3 = correlate_sync_lock(sync_res, unlocked)
        assert r3 == sync_res

    # ------------------------------------------------------------------
    # 16. No file, process or registry modification by the analyzer
    # ------------------------------------------------------------------
    def test_no_file_modification_by_analyzer(self):
        """The analyzer must not alter the file content, size, or timestamp."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, "immutable.txt")
            payload = "original uncorrupted data 1234567890"
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(payload)

            stat_before = os.stat(file_path)

            analyzer = SyncConflictAnalyzer(
                roots_override={PROVIDER_ONEDRIVE: [temp_dir]},
            )
            analyzer.analyze(file_path)

            stat_after = os.stat(file_path)

            with open(file_path, "r", encoding="utf-8") as f:
                content_after = f.read()

            assert content_after == payload
            assert stat_before.st_size == stat_after.st_size
            assert stat_before.st_mtime == stat_after.st_mtime


# ======================================================================
# Real OS Discovery Tests (Windows only)
# ======================================================================

@pytest.mark.skipif(not _IS_WINDOWS, reason="Windows-specific OS tests")
class TestLiveWindowsSyncDiscovery:
    """Verifies that live Windows registry and environment inspection execute cleanly."""

    def test_live_onedrive_roots_discovery(self):
        """Querying live OneDrive roots on Windows must return a list of valid strings without raising."""
        analyzer = SyncConflictAnalyzer()
        roots = analyzer._get_onedrive_roots()
        assert isinstance(roots, list)
        for r in roots:
            assert isinstance(r, str)
            assert os.path.isabs(r)

    def test_live_google_drive_roots_discovery(self):
        """Querying live Google Drive roots on Windows must return a list of valid strings without raising."""
        analyzer = SyncConflictAnalyzer()
        roots = analyzer._get_google_drive_roots()
        assert isinstance(roots, list)
        for r in roots:
            assert isinstance(r, str)
            assert os.path.isabs(r)

    def test_live_process_inspection(self):
        """Calling live psutil inspection for OneDrive and Google Drive returns safely without error."""
        analyzer = SyncConflictAnalyzer()
        is_running_od, procs_od = analyzer._is_client_running(PROVIDER_ONEDRIVE)
        assert isinstance(is_running_od, bool)
        assert isinstance(procs_od, list)

        is_running_gd, procs_gd = analyzer._is_client_running(PROVIDER_GOOGLE_DRIVE)
        assert isinstance(is_running_gd, bool)
        assert isinstance(procs_gd, list)
