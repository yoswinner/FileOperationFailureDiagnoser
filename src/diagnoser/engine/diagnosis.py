"""
Rule-Based Diagnosis Engine.

Orchestrates the four peer analyzers:
    1. ProcessLockAnalyzer      — active file handle and locker detection
    2. PermissionAnalyzer       — effective access rights and owner resolution
    3. FileAttributeAnalyzer    — filesystem attributes (readonly, hidden, system, offline)
    4. SyncConflictAnalyzer     — cloud-sync root association and conflict analysis

Consolidates their structured evidence, applies a deterministic priority
decision policy, and attaches actionable guidance from the standalone Recommender.

Decision Priority Order:
    1. FILE_NOT_FOUND   — file does not exist on disk (skips downstream checks)
    2. SYNC_CONFLICT    — confirmed lock held by a supported cloud-sync daemon
    3. FILE_LOCKED      — file held by an ordinary application process
    4. READ_ONLY        — write/delete blocked by read-only attribute or permissions
    5. PERMISSION_DENIED — requested operation denied by filesystem permissions
    6. OPERATION_ALLOWED — all checks completed with no blocking condition detected
    7. UNKNOWN_ERROR    — critical inspection failure or indeterminate state

Safety Policy:
    Strictly read-only and non-destructive. Never terminates processes, never modifies
    files or attributes, and never alters registry or permission configurations.
"""

import os
from typing import Optional, Tuple

from diagnoser.analyzers.file_attributes import FileAttributeAnalyzer
from diagnoser.analyzers.permissions import PermissionAnalyzer
from diagnoser.analyzers.process_lock import ProcessLockAnalyzer
from diagnoser.analyzers.sync_conflict import SyncConflictAnalyzer, correlate_sync_lock
from diagnoser.models import (
    DiagnosisResult,
    DiagnosisType,
    FileAttributeResult,
    FileOperation,
    LockDetectionResult,
    PermissionCheckResult,
    SyncConflictResult,
)
from diagnoser.recommendations.recommender import Recommender


PROVIDER_DISPLAY_NAMES = {
    "onedrive": "OneDrive",
    "google_drive": "Google Drive",
}


class DiagnosisEngine:
    """Produces a human-readable diagnosis for a file operation.

    Runs the four peer analyzers and produces a single, ranked DiagnosisResult
    identifying the primary reason a requested file operation would fail,
    while attaching all supporting structured evidence.

    Usage:
        engine = DiagnosisEngine()
        result = engine.diagnose(r"C:\\data.txt", FileOperation.WRITE)
        print(result.diagnosis)         # DiagnosisType.FILE_LOCKED
        print(result.reason)            # "File is currently locked by ..."
        print(result.suggested_action)  # Actionable advice from Recommender
    """

    def __init__(
        self,
        lock_analyzer: Optional[ProcessLockAnalyzer] = None,
        permission_analyzer: Optional[PermissionAnalyzer] = None,
        attribute_analyzer: Optional[FileAttributeAnalyzer] = None,
        sync_analyzer: Optional[SyncConflictAnalyzer] = None,
        recommender: Optional[Recommender] = None,
    ):
        """Initialise the engine with optional analyzer overrides.

        Args:
            lock_analyzer: ProcessLockAnalyzer instance or override.
            permission_analyzer: PermissionAnalyzer instance or override.
            attribute_analyzer: FileAttributeAnalyzer instance or override.
            sync_analyzer: SyncConflictAnalyzer instance or override.
            recommender: Recommender instance or override.
        """
        self._lock_analyzer = lock_analyzer or ProcessLockAnalyzer()
        self._perm_analyzer = permission_analyzer or PermissionAnalyzer()
        self._attr_analyzer = attribute_analyzer or FileAttributeAnalyzer()
        self._sync_analyzer = sync_analyzer or SyncConflictAnalyzer()
        self._recommender = recommender or Recommender()

    def diagnose(
        self,
        file_path: str,
        operation: FileOperation = FileOperation.READ,
    ) -> DiagnosisResult:
        """Run the diagnosis pipeline for *file_path* and *operation*.

        Args:
            file_path: Path to the target file.
            operation: The intended file operation (READ, WRITE, EXECUTE, DELETE).

        Returns:
            DiagnosisResult containing primary diagnosis, human-readable reason,
            recommender advice, and all four raw analyzer results.
        """
        # Normalise path and operation
        file_path = os.path.abspath(os.path.normpath(file_path))
        if isinstance(operation, str):
            try:
                operation = FileOperation(operation.lower())
            except ValueError:
                operation = FileOperation.READ
        op_str = operation.value

        # ── Step 1: Missing Target (FILE_NOT_FOUND) ──────────────────
        if not os.path.exists(file_path):
            result = DiagnosisResult(
                file_path=file_path,
                operation=op_str,
                diagnosis=DiagnosisType.FILE_NOT_FOUND,
                reason="The specified file does not exist.",
                suggested_action="",
                lock_result=None,
                permission_result=None,
                attribute_result=None,
                sync_result=None,
            )
            result.suggested_action = self._recommender.recommend(result)
            return result

        # ── Step 2: Directory Target Handling ────────────────────────
        if os.path.isdir(file_path):
            lock_res = self._safe_analyze_lock(file_path)
            perm_res = self._safe_analyze_perm(file_path, operation)
            attr_res = self._safe_analyze_attr(file_path)
            sync_res = self._safe_analyze_sync(file_path)

            result = DiagnosisResult(
                file_path=file_path,
                operation=op_str,
                diagnosis=DiagnosisType.UNKNOWN_ERROR,
                reason="The specified path is a directory, not a regular file.",
                suggested_action="",
                lock_result=lock_res,
                permission_result=perm_res,
                attribute_result=attr_res,
                sync_result=sync_res,
            )
            result.suggested_action = self._recommender.recommend(result)
            return result

        # ── Step 3: Run All Four Peer Analyzers ──────────────────────
        lock_res = self._safe_analyze_lock(file_path)
        perm_res = self._safe_analyze_perm(file_path, operation)
        attr_res = self._safe_analyze_attr(file_path)
        sync_res = self._safe_analyze_sync(file_path)

        # ── Step 4: Lock Correlation ────────────────────────────────
        # Correlate lock findings with sync provider findings
        sync_res = correlate_sync_lock(sync_res, lock_res)

        # ── Step 5: Deterministic Priority Classification ───────────
        diagnosis_type, primary_reason = self._classify(
            operation, lock_res, perm_res, attr_res, sync_res
        )

        # ── Step 6: Build Secondary Context ─────────────────────────
        secondary_notes = []
        if diagnosis_type != DiagnosisType.SYNC_CONFLICT and sync_res:
            prov = PROVIDER_DISPLAY_NAMES.get(
                (sync_res.provider or "").lower(), (sync_res.provider or "cloud sync").capitalize()
            )
            if sync_res.evidence_level == "potential_contention":
                secondary_notes.append(f"Located in {prov} folder with client running")
            elif sync_res.is_synced:
                secondary_notes.append(f"Located in {prov} folder")

        if diagnosis_type != DiagnosisType.READ_ONLY and attr_res and attr_res.is_readonly:
            if operation in (FileOperation.WRITE, FileOperation.DELETE):
                secondary_notes.append("File also has the read-only attribute set")

        if diagnosis_type not in (DiagnosisType.FILE_LOCKED, DiagnosisType.SYNC_CONFLICT) and lock_res and lock_res.is_locked:
            secondary_notes.append("File is also locked by an active process")

        if diagnosis_type == DiagnosisType.PERMISSION_DENIED and lock_res and lock_res.error:
            secondary_notes.append(f"Lock inspection could not complete: {lock_res.error}")

        if secondary_notes:
            full_reason = f"{primary_reason} ({'; '.join(secondary_notes)}.)"
        else:
            full_reason = primary_reason

        # ── Step 7: Assemble Result and Recommender Guidance ─────────
        result = DiagnosisResult(
            file_path=file_path,
            operation=op_str,
            diagnosis=diagnosis_type,
            reason=full_reason,
            suggested_action="",
            lock_result=lock_res,
            permission_result=perm_res,
            attribute_result=attr_res,
            sync_result=sync_res,
        )

        result.suggested_action = self._recommender.recommend(result)
        return result

    # ------------------------------------------------------------------
    # Defensive Analyzer Execution Wrappers
    # ------------------------------------------------------------------

    def _safe_analyze_lock(self, path: str) -> LockDetectionResult:
        try:
            return self._lock_analyzer.analyze(path)
        except Exception as exc:
            return LockDetectionResult(
                file_path=path,
                is_locked=False,
                error=f"Lock analysis error: {exc}",
                detection_method="error",
            )

    def _safe_analyze_perm(self, path: str, op: FileOperation) -> PermissionCheckResult:
        try:
            return self._perm_analyzer.analyze(path, op)
        except Exception as exc:
            return PermissionCheckResult(
                file_path=path,
                operation=op.value if isinstance(op, FileOperation) else str(op),
                permitted=False,
                error=f"Permission analysis error: {exc}",
                detection_method="error",
            )

    def _safe_analyze_attr(self, path: str) -> FileAttributeResult:
        try:
            return self._attr_analyzer.analyze(path)
        except Exception as exc:
            return FileAttributeResult(
                file_path=path,
                error=f"Attribute analysis error: {exc}",
                detection_method="error",
            )

    def _safe_analyze_sync(self, path: str) -> SyncConflictResult:
        try:
            return self._sync_analyzer.analyze(path)
        except Exception as exc:
            return SyncConflictResult(
                file_path=path,
                error=f"Sync conflict analysis error: {exc}",
                detection_method="error",
            )

    # ------------------------------------------------------------------
    # Priority Decision Logic
    # ------------------------------------------------------------------

    def _classify(
        self,
        operation: FileOperation,
        lock_res: LockDetectionResult,
        perm_res: PermissionCheckResult,
        attr_res: FileAttributeResult,
        sync_res: SyncConflictResult,
    ) -> Tuple[DiagnosisType, str]:
        """Classify primary failure root cause according to deterministic priority."""
        # 1. Confirmed sync conflict lock (holding process matches OneDrive or Google Drive)
        if sync_res and sync_res.is_conflict:
            return DiagnosisType.SYNC_CONFLICT, self._build_sync_conflict_reason(sync_res)

        # 2. Confirmed application process lock (Restart Manager detected active handles)
        if lock_res and lock_res.is_locked:
            return DiagnosisType.FILE_LOCKED, self._build_lock_reason(lock_res)

        # 3. Read-only restriction (relevant for WRITE and DELETE)
        if operation in (FileOperation.WRITE, FileOperation.DELETE):
            is_ro = False
            if attr_res and attr_res.is_readonly is True:
                is_ro = True
            elif perm_res and not perm_res.permitted and perm_res.detection_method != "error":
                bits = perm_res.permission_bits or {}
                if bits.get("read", False) and not bits.get("write", False):
                    is_ro = True

            if is_ro:
                reason = (
                    f"The file is read-only. The current user cannot "
                    f"{operation.value} this file."
                )
                return DiagnosisType.READ_ONLY, reason

        # 4. Proven permission denial (independent verified evidence from Permission Analyzer)
        if perm_res and not perm_res.permitted and perm_res.detection_method != "error":
            return DiagnosisType.PERMISSION_DENIED, self._build_permission_reason(operation, perm_res)

        # 5. Critical inspection failures (precede success when inspection was blocked/impossible)
        if perm_res and perm_res.error and perm_res.detection_method == "error":
            return DiagnosisType.UNKNOWN_ERROR, f"Permission inspection error: {perm_res.error}"
        if lock_res and lock_res.error and lock_res.detection_method == "error":
            return DiagnosisType.UNKNOWN_ERROR, f"Lock inspection error: {lock_res.error}"

        # 6. Fallback permission check (if any other permission failure was reported)
        if perm_res and not perm_res.permitted:
            return DiagnosisType.PERMISSION_DENIED, self._build_permission_reason(operation, perm_res)

        # 7. No blocking condition detected
        return (
            DiagnosisType.OPERATION_ALLOWED,
            "The requested operation is permitted and no lock was detected.",
        )

    # ------------------------------------------------------------------
    # Reason String Builders
    # ------------------------------------------------------------------

    @staticmethod
    def _build_lock_reason(lock_result: LockDetectionResult) -> str:
        """Build human-readable reason string from lock results."""
        if not lock_result.processes:
            return "File is currently locked by another process."

        parts = []
        for proc in lock_result.processes:
            name = proc.process_name or "(unknown)"
            parts.append(f"{name} (PID {proc.pid})")

        if len(parts) == 1:
            return f"File is currently locked by {parts[0]}."
        return "File is currently locked by: " + ", ".join(parts) + "."

    @staticmethod
    def _build_sync_conflict_reason(sync_result: SyncConflictResult) -> str:
        """Build human-readable reason string from confirmed sync conflict results."""
        prov = PROVIDER_DISPLAY_NAMES.get(
            (sync_result.provider or "").lower(), (sync_result.provider or "cloud sync").capitalize()
        )
        if sync_result.locking_process:
            p = sync_result.locking_process
            name = p.process_name or "(unknown)"
            return (
                f"File is locked by {prov} process {name} (PID {p.pid}) "
                "during active synchronization."
            )
        return f"File is currently in conflict with {prov} synchronization."

    @staticmethod
    def _build_permission_reason(
        operation: FileOperation,
        perm_result: PermissionCheckResult,
    ) -> str:
        """Build human-readable reason for permission denial."""
        op_label = operation.value.upper()
        if perm_result.owner:
            return (
                f"The current user does not have {op_label} permission. "
                f"File owner: {perm_result.owner}."
            )
        return f"The current user does not have {op_label} permission."
