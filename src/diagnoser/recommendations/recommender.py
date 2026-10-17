"""
Recommendation Generator.

Generates safe, human-readable recommendations based on structured
diagnostic results and operating-system evidence.

Safety Policy:
    The recommender is strictly advisory. It NEVER suggests actions that
    automatically modify the system, kill processes, or alter file
    permissions. All recommendations are designed to guide the user in
    making safe, informed decisions.
"""

from typing import Any, Dict, List, Optional, Union

from diagnoser.models import (
    DiagnosisResult,
    DiagnosisType,
    FileAttributeResult,
    LockDetectionResult,
    PermissionCheckResult,
    ProcessInfo,
    SyncConflictResult,
)


class Recommender:
    """Generates safe, actionable recommendations from a diagnosis.

    Evaluates the primary diagnosis category alongside raw analyzer evidence
    (process locks, permissions, file attributes, sync conflicts) to provide
    context-aware advice without fabricating details.

    Usage:
        recommender = Recommender()
        advice = recommender.recommend(diagnosis_result)
        print(advice)
    """

    def recommend(
        self,
        diagnosis: Union[DiagnosisResult, DiagnosisType, Dict[str, Any], str],
    ) -> str:
        """Generate a safe, human-readable recommendation.

        Args:
            diagnosis: A DiagnosisResult instance, DiagnosisType enum,
                       dictionary representation, or string diagnosis name.

        Returns:
            A human-readable recommendation string.
        """
        diag_type, lock_res, perm_res, attr_res, sync_res = self._extract_context(
            diagnosis
        )

        if diag_type == DiagnosisType.FILE_NOT_FOUND:
            return self._recommend_file_not_found()

        elif diag_type == DiagnosisType.FILE_LOCKED:
            return self._recommend_file_locked(lock_res)

        elif diag_type == DiagnosisType.READ_ONLY:
            return self._recommend_read_only(attr_res)

        elif diag_type == DiagnosisType.PERMISSION_DENIED:
            return self._recommend_permission_denied(perm_res)

        elif diag_type == DiagnosisType.SYNC_CONFLICT:
            return self._recommend_sync_conflict(sync_res, lock_res)

        elif diag_type == DiagnosisType.OPERATION_ALLOWED:
            return self._recommend_operation_allowed()

        else:
            return self._recommend_unknown()

    def recommend_actions(
        self,
        diagnosis: Union[DiagnosisResult, DiagnosisType, Dict[str, Any], str],
    ) -> List[str]:
        """Generate a list of actionable recommendation steps.

        Args:
            diagnosis: The diagnostic result or context.

        Returns:
            A list of discrete recommendation strings.
        """
        primary = self.recommend(diagnosis)
        return [primary] if primary else []

    # ------------------------------------------------------------------
    # Category-specific recommendation strategies
    # ------------------------------------------------------------------

    @staticmethod
    def _recommend_file_not_found() -> str:
        return (
            "Verify the file path is correct and ensure the file has "
            "not been moved, renamed, or deleted."
        )

    @staticmethod
    def _recommend_file_locked(
        lock_res: Optional[LockDetectionResult],
    ) -> str:
        if lock_res and lock_res.processes:
            procs = lock_res.processes
            if len(procs) == 1:
                p = procs[0]
                name = p.process_name or "(unknown process)"
                return (
                    f"Save your work in {name} (PID {p.pid}) and close "
                    "the application before retrying the operation."
                )
            else:
                proc_strs = [
                    f"{p.process_name or '(unknown)'} (PID {p.pid})"
                    for p in procs
                ]
                proc_list = ", ".join(proc_strs)
                return (
                    "Save your work and close the applications currently "
                    f"using this file: {proc_list}."
                )

        return (
            "Save your work and close the application currently holding "
            "the file open, then retry the operation."
        )

    @staticmethod
    def _recommend_read_only(
        attr_res: Optional[FileAttributeResult],
    ) -> str:
        return (
            "The file is marked read-only. In File Explorer, right-click the "
            "file, select Properties, and review whether to uncheck the "
            "'Read-only' attribute before retrying."
        )

    @staticmethod
    def _recommend_permission_denied(
        perm_res: Optional[PermissionCheckResult],
    ) -> str:
        if perm_res and perm_res.owner:
            return (
                f"Check the file's NTFS permissions in File Explorer "
                f"(Properties > Security) or contact the file owner "
                f"({perm_res.owner}) or an administrator to request access."
            )
        return (
            "Check the file's NTFS permissions in File Explorer "
            "(Properties > Security) or contact an administrator to request access."
        )

    @staticmethod
    def _recommend_sync_conflict(
        sync_res: Optional[SyncConflictResult],
        lock_res: Optional[LockDetectionResult],
    ) -> str:
        raw_prov = (sync_res.provider if sync_res and sync_res.provider else "cloud sync").lower()
        if raw_prov == "onedrive":
            provider = "OneDrive"
        elif raw_prov == "google_drive":
            provider = "Google Drive"
        else:
            provider = raw_prov.capitalize()

        # If a lock was confirmed by lock analysis or sync result
        if (sync_res and sync_res.is_conflict) or (lock_res and lock_res.is_locked):
            return (
                f"Wait a few moments for {provider} to finish synchronizing, "
                f"or check the {provider} status in the system tray. If necessary, "
                "temporarily pause syncing before modifying the file."
            )

        # Mere association without confirmed lock
        if sync_res and sync_res.is_synced:
            return (
                f"The file is stored inside a {provider} folder, but no active sync "
                "lock was confirmed. Check if the sync client is currently uploading "
                "or downloading changes."
            )

        return (
            "Wait for background cloud synchronization to complete, or check your "
            "sync client status before retrying."
        )

    @staticmethod
    def _recommend_operation_allowed() -> str:
        return "No blocking condition detected. The requested operation is permitted to proceed."

    @staticmethod
    def _recommend_unknown() -> str:
        return (
            "Unable to determine the exact failure cause from available evidence. "
            "Ensure the file path is accessible and consider running with appropriate "
            "administrative privileges."
        )

    # ------------------------------------------------------------------
    # Context extraction helper
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_context(
        diagnosis: Union[DiagnosisResult, DiagnosisType, Dict[str, Any], str],
    ):
        """Extract diagnosis type and analyzer results from various input types."""
        diag_type: Optional[DiagnosisType] = None
        lock_res: Optional[LockDetectionResult] = None
        perm_res: Optional[PermissionCheckResult] = None
        attr_res: Optional[FileAttributeResult] = None
        sync_res: Optional[SyncConflictResult] = None

        if isinstance(diagnosis, DiagnosisResult):
            diag_type = diagnosis.diagnosis
            lock_res = diagnosis.lock_result
            perm_res = diagnosis.permission_result
            attr_res = diagnosis.attribute_result
            sync_res = diagnosis.sync_result

        elif isinstance(diagnosis, DiagnosisType):
            diag_type = diagnosis

        elif isinstance(diagnosis, dict):
            raw_type = diagnosis.get("diagnosis")
            if isinstance(raw_type, DiagnosisType):
                diag_type = raw_type
            elif isinstance(raw_type, str):
                for dt in DiagnosisType:
                    if dt.value == raw_type or dt.name == raw_type:
                        diag_type = dt
                        break
            lock_res = diagnosis.get("lock_result")
            perm_res = diagnosis.permission_result if hasattr(diagnosis, "permission_result") else diagnosis.get("permission_result")
            attr_res = diagnosis.get("attribute_result")
            sync_res = diagnosis.get("sync_result")

        elif isinstance(diagnosis, str):
            for dt in DiagnosisType:
                if dt.value == diagnosis or dt.name == diagnosis:
                    diag_type = dt
                    break

        if diag_type is None:
            diag_type = DiagnosisType.UNKNOWN_ERROR

        return diag_type, lock_res, perm_res, attr_res, sync_res
