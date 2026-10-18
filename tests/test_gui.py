"""
Tests for Tkinter Desktop GUI (MainWindow) in the File Operation Failure Diagnoser.

Verifies:
  1. Accessible file with normal analyzer results (OPERATION_ALLOWED).
  2. Missing file display (FILE_NOT_FOUND — clear indication of skipped checks).
  3. Locked file with real returned process data (FILE_LOCKED).
  4. Permission-restricted file (PERMISSION_DENIED).
  5. Read-only attribute on write/delete operations (READ_ONLY).
  6. Hidden, system, and archive attributes without false error attribution.
  7. OneDrive path association without a confirmed lock (path_only).
  8. Google Drive association with client daemon running (potential_contention).
  9. Confirmed sync-client lock (SYNC_CONFLICT).
 10. Multiple simultaneous findings (primary priority with secondary evidence).
 11. Analyzer errors and unknown/unavailable data representation.
 12. Complete panel reset between diagnoses (no stale data leakage).
 13. Empty process list and unavailable process executable path.
 14. Long paths and lengthy diagnostic messages.
 15. End-to-end diagnosis execution via injected mock engine.
"""

import tkinter as tk
from unittest.mock import MagicMock, patch
import pytest

from diagnoser.gui.main_window import (
    MainWindow,
    SYNC_EVIDENCE_LABELS,
    SYNC_PROVIDER_NAMES,
    _COLOURS,
)
from diagnoser.models import (
    DiagnosisResult,
    DiagnosisType,
    FileAttributeResult,
    FileOperation,
    LockDetectionResult,
    PermissionCheckResult,
    ProcessInfo,
    SyncConflictResult,
)


@pytest.fixture(scope="module")
def tk_window():
    """Create a hidden MainWindow instance for headless testing."""
    root = tk.Tk()
    root.withdraw()
    mock_engine = MagicMock()
    window = MainWindow(engine=mock_engine, root=root)
    yield window
    try:
        root.destroy()
    except Exception:
        pass


@pytest.fixture(autouse=True)
def reset_window_state(tk_window):
    """Ensure clean panel and mock state before each test."""
    tk_window._engine.reset_mock()
    tk_window._file_var.set("")
    tk_window._op_var.set(FileOperation.READ.value.upper())
    tk_window._reset_panels()


class TestMainWindowIntegration:
    """Tests covering all 14 GUI integration and display scenarios."""

    def test_01_accessible_file_operation_allowed(self, tk_window):
        """Scenario 1: Accessible file with normal results renders OPERATION_ALLOWED."""
        result = DiagnosisResult(
            file_path=r"C:\test\sample.txt",
            operation="read",
            diagnosis=DiagnosisType.OPERATION_ALLOWED,
            reason="The requested operation is permitted and no lock was detected.",
            suggested_action="No action required.",
            lock_result=LockDetectionResult(
                file_path=r"C:\test\sample.txt",
                is_locked=False,
                processes=[],
                detection_method="restart_manager",
            ),
            permission_result=PermissionCheckResult(
                file_path=r"C:\test\sample.txt",
                operation="read",
                permitted=True,
                owner=r"DOMAIN\User",
                current_user="User",
                permission_bits={"read": True, "write": True, "execute": False},
                detection_method="windows_acl",
            ),
            attribute_result=FileAttributeResult(
                file_path=r"C:\test\sample.txt",
                is_readonly=False,
                is_hidden=False,
                is_system=False,
                is_archive=True,
                is_reparse_point=False,
                is_offline=False,
                raw_attributes=0x0020,
                attributes_list=["ARCHIVE"],
                detection_method="windows_api",
            ),
            sync_result=SyncConflictResult(
                file_path=r"C:\test\sample.txt",
                is_synced=False,
                provider="",
                sync_root="",
                client_running=False,
                evidence_level="none",
                details="File is outside any detected cloud sync directory.",
                detection_method="local_sync_detection",
            ),
        )

        tk_window._update_status(result)
        tk_window._update_process_list(result)
        tk_window._update_permissions(result)
        tk_window._update_attributes(result)
        tk_window._update_sync(result)
        tk_window._update_recommendation(result)

        # Status panel
        assert "OPERATION ALLOWED" in tk_window._status_badge.cget("text")
        assert str(tk_window._status_badge.cget("background")) == _COLOURS["green"]
        assert tk_window._status_file_lbl.cget("text") == r"C:\test\sample.txt"
        assert tk_window._status_op_lbl.cget("text") == "READ"

        # Process list
        assert len(tk_window._proc_tree.get_children()) == 0
        assert "No active process locks detected" in tk_window._proc_placeholder.cget("text")

        # Permissions
        assert tk_window._perm_owner_lbl.cget("text") == r"DOMAIN\User"
        assert len(tk_window._perm_bits_frame.winfo_children()) == 3

        # Attributes
        assert "0x0020" in tk_window._attr_raw_lbl.cget("text")
        assert "No attribute restrictions" in tk_window._attr_effect_lbl.cget("text")

        # Sync
        assert tk_window._sync_provider_lbl.cget("text") == "No provider identified"
        assert "No provider association detected" in tk_window._sync_evidence_lbl.cget("text")

        # Recommendation
        assert "No action required." in tk_window._rec_label.cget("text")

    def test_02_missing_file_distinct_from_success(self, tk_window):
        """Scenario 2: Nonexistent file explicitly indicates skipped analysis."""
        result = DiagnosisResult(
            file_path=r"C:\missing\file.txt",
            operation="read",
            diagnosis=DiagnosisType.FILE_NOT_FOUND,
            reason="The specified file does not exist.",
            suggested_action="Verify that the file path is typed correctly.",
            lock_result=None,
            permission_result=None,
            attribute_result=None,
            sync_result=None,
        )

        tk_window._update_status(result)
        tk_window._update_process_list(result)
        tk_window._update_permissions(result)
        tk_window._update_attributes(result)
        tk_window._update_sync(result)
        tk_window._update_recommendation(result)

        # Badge reflects warning / not found
        assert "FILE NOT FOUND" in tk_window._status_badge.cget("text")
        assert str(tk_window._status_badge.cget("background")) == _COLOURS["orange"]

        # All four panels explicitly show skipped checks, NOT success
        assert "lock analysis skipped" in tk_window._proc_placeholder.cget("text").lower()
        assert "permission check skipped" in tk_window._perm_placeholder.cget("text").lower()
        assert "attribute check skipped" in tk_window._attr_placeholder.cget("text").lower()
        assert "sync check skipped" in tk_window._sync_placeholder.cget("text").lower()

    def test_03_locked_file_displays_real_process_telemetry(self, tk_window):
        """Scenario 3: Active process lock renders holding process name, PID, and executable."""
        proc = ProcessInfo(
            process_name="notepad.exe",
            pid=2048,
            executable_path=r"C:\Windows\System32\notepad.exe",
        )
        result = DiagnosisResult(
            file_path=r"C:\data\report.docx",
            operation="write",
            diagnosis=DiagnosisType.FILE_LOCKED,
            reason="File is currently locked by notepad.exe (PID 2048).",
            suggested_action="Close notepad.exe (PID 2048) or save changes before retrying.",
            lock_result=LockDetectionResult(
                file_path=r"C:\data\report.docx",
                is_locked=True,
                processes=[proc],
                detection_method="restart_manager",
            ),
        )

        tk_window._update_status(result)
        tk_window._update_process_list(result)
        tk_window._update_recommendation(result)

        assert "FILE LOCKED" in tk_window._status_badge.cget("text")
        assert str(tk_window._status_badge.cget("background")) == _COLOURS["red"]

        # Treeview rows populated exactly
        children = tk_window._proc_tree.get_children()
        assert len(children) == 1
        item = tk_window._proc_tree.item(children[0])
        values = item["values"]
        assert values[0] == "notepad.exe"
        assert int(values[1]) == 2048
        assert values[2] == r"C:\Windows\System32\notepad.exe"

    def test_04_permission_restricted_file_presentation(self, tk_window):
        """Scenario 4: Permission-restricted file shows owner, bits, and honesty disclaimer."""
        result = DiagnosisResult(
            file_path=r"C:\secure\audit.log",
            operation="delete",
            diagnosis=DiagnosisType.PERMISSION_DENIED,
            reason=r"The current user does not have DELETE permission. File owner: NT SERVICE\TrustedInstaller.",
            suggested_action="Request elevated permissions from the file owner or administrator.",
            permission_result=PermissionCheckResult(
                file_path=r"C:\secure\audit.log",
                operation="delete",
                permitted=False,
                owner=r"NT SERVICE\TrustedInstaller",
                current_user="StandardUser",
                permission_bits={"read": True, "write": False, "execute": False, "delete": False},
                detection_method="windows_acl",
            ),
        )

        tk_window._update_status(result)
        tk_window._update_permissions(result)

        assert "PERMISSION DENIED" in tk_window._status_badge.cget("text")
        assert str(tk_window._status_badge.cget("background")) == _COLOURS["red"]
        assert tk_window._perm_owner_lbl.cget("text") == r"NT SERVICE\TrustedInstaller"
        assert tk_window._perm_user_lbl.cget("text") == "StandardUser"
        # Honest disclaimer present
        assert "full NTFS DACL not evaluated" in tk_window._perm_method_lbl.cget("text")

    def test_05_readonly_attribute_write_operation(self, tk_window):
        """Scenario 5: Read-only flag on write operation explains attribute blocker."""
        result = DiagnosisResult(
            file_path=r"C:\config\settings.ini",
            operation="write",
            diagnosis=DiagnosisType.READ_ONLY,
            reason="The file is read-only. The current user cannot write this file.",
            suggested_action="Clear the Read-only checkbox in the file's Properties dialog.",
            attribute_result=FileAttributeResult(
                file_path=r"C:\config\settings.ini",
                is_readonly=True,
                is_hidden=False,
                is_system=False,
                is_archive=True,
                is_reparse_point=False,
                is_offline=False,
                raw_attributes=0x0021,
                attributes_list=["READONLY", "ARCHIVE"],
                detection_method="windows_api",
            ),
        )

        tk_window._update_status(result)
        tk_window._update_attributes(result)

        assert "READ ONLY" in tk_window._status_badge.cget("text")
        assert str(tk_window._status_badge.cget("background")) == _COLOURS["orange"]
        assert "0x0021" in tk_window._attr_raw_lbl.cget("text")
        assert "prevents WRITE operations" in tk_window._attr_effect_lbl.cget("text")

    def test_06_hidden_system_archive_attributes_not_flagged_as_errors(self, tk_window):
        """Scenario 6: Hidden, system, and archive flags displayed without false error claims."""
        result = DiagnosisResult(
            file_path=r"C:\boot\bootstat.dat",
            operation="read",
            diagnosis=DiagnosisType.OPERATION_ALLOWED,
            reason="Operation permitted.",
            attribute_result=FileAttributeResult(
                file_path=r"C:\boot\bootstat.dat",
                is_readonly=False,
                is_hidden=True,
                is_system=True,
                is_archive=True,
                is_reparse_point=False,
                is_offline=False,
                raw_attributes=0x0026,
                attributes_list=["HIDDEN", "SYSTEM", "ARCHIVE"],
                detection_method="windows_api",
            ),
        )

        tk_window._update_attributes(result)

        # 6 flags rendered inside grid
        flag_cells = tk_window._attr_bits_frame.winfo_children()
        assert len(flag_cells) == 6

        # Effect should NOT state an error occurred
        assert "No attribute restrictions blocking READ operation" in tk_window._attr_effect_lbl.cget("text")

    def test_07_onedrive_path_association_without_confirmed_lock(self, tk_window):
        """Scenario 7: OneDrive path association alone does not claim an active lock."""
        result = DiagnosisResult(
            file_path=r"C:\Users\John\OneDrive\Documents\notes.txt",
            operation="write",
            diagnosis=DiagnosisType.OPERATION_ALLOWED,
            reason="Operation permitted.",
            sync_result=SyncConflictResult(
                file_path=r"C:\Users\John\OneDrive\Documents\notes.txt",
                is_synced=True,
                provider="onedrive",
                sync_root=r"C:\Users\John\OneDrive",
                client_running=False,
                evidence_level="path_only",
                details="File resides in OneDrive directory; client daemon is not running.",
                detection_method="local_sync_detection",
            ),
        )

        tk_window._update_sync(result)

        assert tk_window._sync_provider_lbl.cget("text") == "Microsoft OneDrive"
        assert tk_window._sync_root_lbl.cget("text") == r"C:\Users\John\OneDrive"
        assert "Not running / Not detected" in tk_window._sync_client_lbl.cget("text")
        assert tk_window._sync_evidence_lbl.cget("text") == "Sync-folder association detected"

    def test_08_google_drive_association_with_client_running(self, tk_window):
        """Scenario 8: Google Drive potential contention with client running."""
        result = DiagnosisResult(
            file_path=r"G:\My Drive\Project\code.py",
            operation="write",
            diagnosis=DiagnosisType.OPERATION_ALLOWED,
            reason="Operation permitted.",
            sync_result=SyncConflictResult(
                file_path=r"G:\My Drive\Project\code.py",
                is_synced=True,
                provider="google_drive",
                sync_root=r"G:\My Drive",
                client_running=True,
                evidence_level="potential_contention",
                details="File resides in Google Drive directory with active client.",
                detection_method="local_sync_detection",
            ),
        )

        tk_window._update_sync(result)

        assert tk_window._sync_provider_lbl.cget("text") == "Google Drive"
        assert tk_window._sync_root_lbl.cget("text") == r"G:\My Drive"
        assert "Running (active background process)" in tk_window._sync_client_lbl.cget("text")
        assert tk_window._sync_evidence_lbl.cget("text") == "Potential contention; active lock not confirmed"

    def test_09_confirmed_sync_client_lock(self, tk_window):
        """Scenario 9: Confirmed lock held by OneDrive daemon displays SYNC_CONFLICT."""
        locker = ProcessInfo(process_name="OneDrive.exe", pid=5678, executable_path=r"C:\AppData\OneDrive.exe")
        result = DiagnosisResult(
            file_path=r"C:\Users\John\OneDrive\syncing.dat",
            operation="write",
            diagnosis=DiagnosisType.SYNC_CONFLICT,
            reason="File is locked by OneDrive process OneDrive.exe (PID 5678) during active synchronization.",
            suggested_action="Wait for Microsoft OneDrive to finish syncing this file before editing it.",
            sync_result=SyncConflictResult(
                file_path=r"C:\Users\John\OneDrive\syncing.dat",
                is_synced=True,
                provider="onedrive",
                sync_root=r"C:\Users\John\OneDrive",
                client_running=True,
                evidence_level="confirmed_lock",
                is_conflict=True,
                locking_process=locker,
                details="Active lock confirmed by OneDrive.exe",
                detection_method="local_sync_detection",
            ),
        )

        tk_window._update_status(result)
        tk_window._update_sync(result)
        tk_window._update_recommendation(result)

        assert "SYNC CONFLICT" in tk_window._status_badge.cget("text")
        assert tk_window._sync_evidence_lbl.cget("text") == "Confirmed sync-client lock"
        assert "OneDrive.exe" in tk_window._sync_details_lbl.cget("text")
        assert "PID 5678" in tk_window._sync_details_lbl.cget("text")
        assert "Microsoft OneDrive to finish syncing" in tk_window._rec_label.cget("text")

    def test_10_multiple_simultaneous_findings_preserve_all_evidence(self, tk_window):
        """Scenario 10: Multi-finding scenario maintains primary lock while showing attributes and sync."""
        proc = ProcessInfo(process_name="WINWORD.EXE", pid=3333, executable_path=r"C:\Office\WINWORD.EXE")
        result = DiagnosisResult(
            file_path=r"C:\Users\John\OneDrive\proposal.docx",
            operation="write",
            diagnosis=DiagnosisType.FILE_LOCKED,
            reason="File is currently locked by WINWORD.EXE (PID 3333). (Located in OneDrive folder with client running; File also has the read-only attribute set.)",
            suggested_action="Close WINWORD.EXE (PID 3333) or save changes before retrying.",
            lock_result=LockDetectionResult(
                file_path=r"C:\Users\John\OneDrive\proposal.docx",
                is_locked=True,
                processes=[proc],
                detection_method="restart_manager",
            ),
            attribute_result=FileAttributeResult(
                file_path=r"C:\Users\John\OneDrive\proposal.docx",
                is_readonly=True,
                is_hidden=False,
                is_system=False,
                is_archive=True,
                raw_attributes=0x0021,
                attributes_list=["READONLY", "ARCHIVE"],
                detection_method="windows_api",
            ),
            sync_result=SyncConflictResult(
                file_path=r"C:\Users\John\OneDrive\proposal.docx",
                is_synced=True,
                provider="onedrive",
                sync_root=r"C:\Users\John\OneDrive",
                client_running=True,
                evidence_level="potential_contention",
                details="File resides in OneDrive folder with active client daemon.",
                detection_method="local_sync_detection",
            ),
        )

        tk_window._update_status(result)
        tk_window._update_process_list(result)
        tk_window._update_attributes(result)
        tk_window._update_sync(result)

        # Primary diagnosis is FILE_LOCKED
        assert "FILE LOCKED" in tk_window._status_badge.cget("text")
        # Process panel shows Word
        assert len(tk_window._proc_tree.get_children()) == 1
        # Attribute panel shows read-only
        assert "0x0021" in tk_window._attr_raw_lbl.cget("text")
        # Cloud sync panel shows OneDrive
        assert tk_window._sync_provider_lbl.cget("text") == "Microsoft OneDrive"

    def test_11_analyzer_error_and_unavailable_data(self, tk_window):
        """Scenario 11: Analyzer errors and unavailable fields are honestly displayed."""
        result = DiagnosisResult(
            file_path=r"C:\test\corrupted.dat",
            operation="read",
            diagnosis=DiagnosisType.UNKNOWN_ERROR,
            reason="Attribute inspection error: Device not ready.",
            attribute_result=FileAttributeResult(
                file_path=r"C:\test\corrupted.dat",
                is_readonly=None,
                is_hidden=None,
                is_system=None,
                is_archive=None,
                is_reparse_point=None,
                is_offline=None,
                error="Device not ready (WinError 21)",
                detection_method="error",
            ),
            sync_result=SyncConflictResult(
                file_path=r"C:\test\corrupted.dat",
                error="Registry access denied",
                detection_method="error",
            ),
        )

        tk_window._update_attributes(result)
        tk_window._update_sync(result)

        # Attribute placeholder shows error
        assert "Device not ready" in tk_window._attr_placeholder.cget("text")
        # Sync placeholder shows error
        assert "Registry access denied" in tk_window._sync_placeholder.cget("text")

        # Unknown attribute flags display 'Unknown / Unavailable'
        flag_cells = tk_window._attr_bits_frame.winfo_children()
        assert len(flag_cells) == 6
        for cell in flag_cells:
            labels = [c for c in cell.winfo_children() if isinstance(c, tk.ttk.Label)]
            assert any("Unknown / Unavailable" in lbl.cget("text") for lbl in labels)

    def test_12_reset_panels_clears_stale_data_completely(self, tk_window):
        """Scenario 12: _reset_panels() wipes all stale data between diagnoses."""
        # 1. First populate with locked file data
        proc = ProcessInfo(process_name="test.exe", pid=9999, executable_path=r"C:\test.exe")
        first_result = DiagnosisResult(
            file_path=r"C:\file1.txt",
            operation="write",
            diagnosis=DiagnosisType.FILE_LOCKED,
            reason="Locked by test.exe",
            suggested_action="Close test.exe",
            lock_result=LockDetectionResult(
                file_path=r"C:\file1.txt",
                is_locked=True,
                processes=[proc],
            ),
            permission_result=PermissionCheckResult(
                file_path=r"C:\file1.txt",
                owner="Admin",
                current_user="User",
                permission_bits={"write": False},
            ),
            attribute_result=FileAttributeResult(
                file_path=r"C:\file1.txt",
                is_readonly=True,
                raw_attributes=0x0001,
            ),
            sync_result=SyncConflictResult(
                file_path=r"C:\file1.txt",
                provider="onedrive",
                sync_root=r"C:\OneDrive",
                evidence_level="potential_contention",
            ),
        )

        tk_window._update_status(first_result)
        tk_window._update_process_list(first_result)
        tk_window._update_permissions(first_result)
        tk_window._update_attributes(first_result)
        tk_window._update_sync(first_result)
        tk_window._update_recommendation(first_result)

        assert len(tk_window._proc_tree.get_children()) == 1
        assert tk_window._perm_owner_lbl.cget("text") == "Admin"
        assert tk_window._sync_provider_lbl.cget("text") == "Microsoft OneDrive"

        # 2. Reset panels
        tk_window._reset_panels()

        assert "WAITING FOR INPUT" in tk_window._status_badge.cget("text")
        assert tk_window._status_file_lbl.cget("text") == "—"
        assert len(tk_window._proc_tree.get_children()) == 0
        assert tk_window._perm_owner_lbl.cget("text") == "—"
        assert len(tk_window._perm_bits_frame.winfo_children()) == 0
        assert tk_window._attr_raw_lbl.cget("text") == "—"
        assert len(tk_window._attr_bits_frame.winfo_children()) == 0
        assert tk_window._sync_provider_lbl.cget("text") == "—"
        assert tk_window._sync_root_lbl.cget("text") == "—"
        assert tk_window._rec_label.cget("text") == "No recommendation available."

    def test_13_empty_process_list_and_unavailable_executable_path(self, tk_window):
        """Scenario 13: Handles unknown process name and unavailable executable path cleanly."""
        proc = ProcessInfo(process_name="", pid=4004, executable_path="")
        result = DiagnosisResult(
            file_path=r"C:\test\handle.dat",
            operation="write",
            diagnosis=DiagnosisType.FILE_LOCKED,
            reason="Locked file",
            lock_result=LockDetectionResult(
                file_path=r"C:\test\handle.dat",
                is_locked=True,
                processes=[proc],
            ),
        )

        tk_window._update_process_list(result)

        children = tk_window._proc_tree.get_children()
        assert len(children) == 1
        values = tk_window._proc_tree.item(children[0])["values"]
        assert values[0] == "(unknown)"
        assert int(values[1]) == 4004
        assert values[2] == "—"

    def test_14_long_paths_and_lengthy_messages_handled_gracefully(self, tk_window):
        """Scenario 14: Extremely long file paths and verbose diagnostics wrap without error."""
        long_path = r"C:\deeply\nested\path\with\many\subdirectories\and\extremely\long\filename_for_testing_file_operation_failure_diagnoser_project_2026_review_3_sprint_4_validation_run.docx"
        long_reason = "This is an extremely long reason explaining why the file operation failed on this system. " * 5
        long_action = "Here is an exhaustive multi-sentence recommendation instructing the administrator on ACL and handle resolution. " * 5

        result = DiagnosisResult(
            file_path=long_path,
            operation="delete",
            diagnosis=DiagnosisType.PERMISSION_DENIED,
            reason=long_reason,
            suggested_action=long_action,
        )

        # Updating should complete cleanly without throwing exceptions or TclErrors
        tk_window._update_status(result)
        tk_window._update_recommendation(result)

        assert tk_window._status_file_lbl.cget("text") == long_path
        assert tk_window._status_reason_lbl.cget("text") == long_reason
        assert tk_window._rec_label.cget("text") == long_action

    def test_15_run_diagnosis_end_to_end_with_mock_engine(self, tk_window):
        """Scenario 15: _run_diagnosis button handler validates input and calls engine."""
        mock_result = DiagnosisResult(
            file_path=r"C:\auto\test.txt",
            operation="read",
            diagnosis=DiagnosisType.OPERATION_ALLOWED,
            reason="Access permitted.",
            suggested_action="No action required.",
        )
        tk_window._engine.diagnose.return_value = mock_result

        # Set input variables
        tk_window._file_var.set(r"C:\auto\test.txt")
        tk_window._op_var.set("READ")

        tk_window._run_diagnosis()

        tk_window._engine.diagnose.assert_called_once_with(
            r"C:\auto\test.txt", FileOperation.READ
        )
        assert "OPERATION ALLOWED" in tk_window._status_badge.cget("text")

    def test_16_run_diagnosis_empty_path_shows_warning(self, tk_window):
        """Scenario 16: Empty file path triggers warning messagebox without calling engine."""
        tk_window._file_var.set("")
        with patch("diagnoser.gui.main_window.messagebox.showwarning") as mock_warn:
            tk_window._run_diagnosis()
            mock_warn.assert_called_once()
            tk_window._engine.diagnose.assert_not_called()
