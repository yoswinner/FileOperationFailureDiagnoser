"""
Unit tests for the Recommender module.

Verifies that the Recommender produces safe, accurate, evidence-grounded
advisory guidance across all diagnosis categories without executing system
actions or fabricating evidence.
"""

import pytest

from diagnoser.models import (
    DiagnosisResult,
    DiagnosisType,
    FileAttributeResult,
    LockDetectionResult,
    PermissionCheckResult,
    ProcessInfo,
    SyncConflictResult,
)
from diagnoser.recommendations.recommender import Recommender

_recommender = Recommender()


# ======================================================================
# FILE_NOT_FOUND Recommendations
# ======================================================================

class TestRecommenderFileNotFound:
    def test_file_not_found_advice(self):
        result = DiagnosisResult(
            file_path="/missing/path/report.docx",
            diagnosis=DiagnosisType.FILE_NOT_FOUND,
        )
        advice = _recommender.recommend(result)
        assert isinstance(advice, str)
        assert "path" in advice.lower()
        assert any(word in advice.lower() for word in ["moved", "deleted", "correct"])

    def test_file_not_found_from_enum(self):
        advice = _recommender.recommend(DiagnosisType.FILE_NOT_FOUND)
        assert "path" in advice.lower()


# ======================================================================
# FILE_LOCKED Recommendations
# ======================================================================

class TestRecommenderFileLocked:
    def test_locked_with_single_process(self):
        """When a single process is identified, mention it by name and PID."""
        lock_res = LockDetectionResult(
            file_path=r"C:\docs\report.docx",
            is_locked=True,
            processes=[ProcessInfo(process_name="WINWORD.EXE", pid=4128)],
        )
        result = DiagnosisResult(
            file_path=r"C:\docs\report.docx",
            diagnosis=DiagnosisType.FILE_LOCKED,
            lock_result=lock_res,
        )
        advice = _recommender.recommend(result)
        assert "WINWORD.EXE" in advice
        assert "4128" in advice
        assert "save" in advice.lower()
        assert "close" in advice.lower()

    def test_locked_with_multiple_processes(self):
        """When multiple lockers exist, list all of them."""
        lock_res = LockDetectionResult(
            file_path=r"C:\data.db",
            is_locked=True,
            processes=[
                ProcessInfo(process_name="app1.exe", pid=101),
                ProcessInfo(process_name="app2.exe", pid=202),
            ],
        )
        result = DiagnosisResult(
            file_path=r"C:\data.db",
            diagnosis=DiagnosisType.FILE_LOCKED,
            lock_result=lock_res,
        )
        advice = _recommender.recommend(result)
        assert "app1.exe" in advice
        assert "101" in advice
        assert "app2.exe" in advice
        assert "202" in advice

    def test_locked_without_process_info(self):
        """When lock detection knows the file is locked but has no PIDs."""
        lock_res = LockDetectionResult(
            file_path=r"C:\data.db",
            is_locked=True,
            processes=[],
        )
        result = DiagnosisResult(
            file_path=r"C:\data.db",
            diagnosis=DiagnosisType.FILE_LOCKED,
            lock_result=lock_res,
        )
        advice = _recommender.recommend(result)
        assert "close the application" in advice.lower()
        # Ensure no fabricated PID is displayed
        assert "PID" not in advice


# ======================================================================
# READ_ONLY Recommendations
# ======================================================================

class TestRecommenderReadOnly:
    def test_read_only_advice(self):
        """Read-only recommendation should suggest inspecting Properties."""
        attr_res = FileAttributeResult(
            file_path=r"C:\docs\readme.txt",
            is_readonly=True,
            attributes_list=["READONLY"],
        )
        result = DiagnosisResult(
            file_path=r"C:\docs\readme.txt",
            diagnosis=DiagnosisType.READ_ONLY,
            attribute_result=attr_res,
        )
        advice = _recommender.recommend(result)
        assert "read-only" in advice.lower()
        assert "properties" in advice.lower()
        assert "uncheck" in advice.lower()


# ======================================================================
# PERMISSION_DENIED Recommendations
# ======================================================================

class TestRecommenderPermissionDenied:
    def test_permission_denied_with_owner(self):
        """When file owner is known, advise contacting the owner."""
        perm_res = PermissionCheckResult(
            file_path=r"C:\secure\file.txt",
            permitted=False,
            owner=r"CORP\Administrator",
            current_user="CORP\\jdoe",
        )
        result = DiagnosisResult(
            file_path=r"C:\secure\file.txt",
            diagnosis=DiagnosisType.PERMISSION_DENIED,
            permission_result=perm_res,
        )
        advice = _recommender.recommend(result)
        assert "CORP\\Administrator" in advice
        assert "permissions" in advice.lower()
        assert "security" in advice.lower()

    def test_permission_denied_without_owner(self):
        """When file owner is unknown, give general administrator advice."""
        perm_res = PermissionCheckResult(
            file_path=r"C:\secure\file.txt",
            permitted=False,
            owner="",
        )
        result = DiagnosisResult(
            file_path=r"C:\secure\file.txt",
            diagnosis=DiagnosisType.PERMISSION_DENIED,
            permission_result=perm_res,
        )
        advice = _recommender.recommend(result)
        assert "administrator" in advice.lower()
        assert "permissions" in advice.lower()


# ======================================================================
# SYNC_CONFLICT Recommendations
# ======================================================================

class TestRecommenderSyncConflict:
    def test_confirmed_sync_lock(self):
        """Confirmed sync conflict advises waiting or checking client tray."""
        sync_res = SyncConflictResult(
            file_path=r"C:\Users\test\OneDrive\doc.docx",
            is_synced=True,
            provider="onedrive",
            is_conflict=True,
        )
        result = DiagnosisResult(
            file_path=r"C:\Users\test\OneDrive\doc.docx",
            diagnosis=DiagnosisType.SYNC_CONFLICT,
            sync_result=sync_res,
        )
        advice = _recommender.recommend(result)
        assert "onedrive" in advice.lower()
        assert "synchronizing" in advice.lower() or "sync" in advice.lower()
        assert "pause" in advice.lower() or "tray" in advice.lower()

    def test_sync_association_only_does_not_claim_confirmed_lock(self):
        """A file merely inside a sync folder must NOT claim a confirmed sync lock."""
        sync_res = SyncConflictResult(
            file_path=r"C:\Users\test\Google Drive\doc.txt",
            is_synced=True,
            provider="google_drive",
            is_conflict=False,  # Not an active lock!
        )
        result = DiagnosisResult(
            file_path=r"C:\Users\test\Google Drive\doc.txt",
            diagnosis=DiagnosisType.SYNC_CONFLICT,
            sync_result=sync_res,
        )
        advice = _recommender.recommend(result)
        # Must clearly indicate that lock was NOT confirmed
        assert "no active sync lock was confirmed" in advice.lower() or "not confirmed" in advice.lower()


# ======================================================================
# OPERATION_ALLOWED & UNKNOWN_ERROR Recommendations
# ======================================================================

class TestRecommenderOtherCategories:
    def test_operation_allowed(self):
        advice = _recommender.recommend(DiagnosisType.OPERATION_ALLOWED)
        assert "permitted" in advice.lower() or "no blocking condition" in advice.lower()

    def test_unknown_error(self):
        advice = _recommender.recommend(DiagnosisType.UNKNOWN_ERROR)
        assert "unable to determine" in advice.lower() or "privileges" in advice.lower()

    def test_recommend_actions_returns_list(self):
        actions = _recommender.recommend_actions(DiagnosisType.OPERATION_ALLOWED)
        assert isinstance(actions, list)
        assert len(actions) == 1
        assert "permitted" in actions[0].lower() or "no blocking condition" in actions[0].lower()

    def test_dict_input_support(self):
        """Recommender should accept dictionary input gracefully."""
        advice = _recommender.recommend({"diagnosis": "file_not_found"})
        assert "path" in advice.lower()

    def test_string_input_support(self):
        """Recommender should accept string diagnosis gracefully."""
        advice = _recommender.recommend("read_only")
        assert "read-only" in advice.lower()
