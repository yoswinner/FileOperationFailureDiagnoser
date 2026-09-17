"""
Rule-Based Diagnosis Engine.

Consumes structured results from the lock and permission analyzers
and produces a single, ranked DiagnosisResult identifying the primary
reason a requested file operation would fail.

Decision order (deterministic, highest-priority first):

    1. FILE_NOT_FOUND  — the file does not exist.
    2. FILE_LOCKED     — a process holds the file open.
    3. PERMISSION_DENIED / READ_ONLY
                       — the current user lacks the required access.
    4. OPERATION_ALLOWED — no issues detected.

The engine delegates all detection to the existing analyzers.
It never calls Windows APIs directly and never modifies the system.

Design:
    - Accepts optional pre-built analyzer instances for testability
      (dependency injection).
    - All Windows-specific logic remains inside the analyzers.
    - The engine is fully deterministic and explainable.
"""

import os

from diagnoser.analyzers.permissions import PermissionAnalyzer
from diagnoser.analyzers.process_lock import ProcessLockAnalyzer
from diagnoser.models import (
    DiagnosisResult,
    DiagnosisType,
    FileOperation,
    LockDetectionResult,
    PermissionCheckResult,
)


class DiagnosisEngine:
    """Produces a human-readable diagnosis for a file operation.

    The engine runs the lock and permission analyzers in order and
    returns a DiagnosisResult classifying the primary failure cause.

    Usage:
        engine = DiagnosisEngine()
        result = engine.diagnose(r"C:\\data.txt", FileOperation.WRITE)
        print(result.diagnosis)   # DiagnosisType.FILE_LOCKED
        print(result.reason)      # "File is currently locked by ..."
        print(result.suggested_action)
    """

    def __init__(
        self,
        lock_analyzer=None,
        permission_analyzer=None,
    ):
        """Initialise the engine with optional analyzer overrides.

        Args:
            lock_analyzer: A ProcessLockAnalyzer instance.  If None,
                           a default instance is created.
            permission_analyzer: A PermissionAnalyzer instance.  If None,
                                 a default instance is created.
        """
        self._lock_analyzer = lock_analyzer or ProcessLockAnalyzer()
        self._perm_analyzer = permission_analyzer or PermissionAnalyzer()

    def diagnose(
        self,
        file_path: str,
        operation: FileOperation = FileOperation.READ,
    ) -> DiagnosisResult:
        """Run the diagnosis pipeline for *file_path* and *operation*.

        Decision order:
            1. Does the file exist?          → FILE_NOT_FOUND
            2. Is the file locked?           → FILE_LOCKED
            3. Is the operation permitted?   → PERMISSION_DENIED / READ_ONLY
            4. All checks pass               → OPERATION_ALLOWED

        Args:
            file_path: Path to the file to diagnose.
            operation: The intended file operation.

        Returns:
            DiagnosisResult with a single primary diagnosis.
        """
        # Normalise path consistently with the analyzers
        file_path = os.path.abspath(os.path.normpath(file_path))

        # ── Step 1: File existence ──────────────────────────────────
        if not os.path.exists(file_path):
            return DiagnosisResult(
                file_path=file_path,
                operation=operation.value,
                diagnosis=DiagnosisType.FILE_NOT_FOUND,
                reason="The specified file does not exist.",
                suggested_action=(
                    "Verify the file path is correct and the file "
                    "has not been moved or deleted."
                ),
            )

        # ── Step 2: Lock detection ──────────────────────────────────
        lock_result = self._lock_analyzer.analyze(file_path)

        if lock_result.is_locked:
            reason = self._build_lock_reason(lock_result)
            return DiagnosisResult(
                file_path=file_path,
                operation=operation.value,
                diagnosis=DiagnosisType.FILE_LOCKED,
                reason=reason,
                suggested_action=(
                    "Close the process holding the file and retry."
                ),
                lock_result=lock_result,
            )

        # ── Step 3: Permission check ────────────────────────────────
        perm_result = self._perm_analyzer.analyze(file_path, operation)

        if not perm_result.permitted:
            # Distinguish READ_ONLY: the user can read but not write/delete
            diagnosis_type = self._classify_permission_failure(
                operation, perm_result,
            )
            reason = self._build_permission_reason(
                operation, diagnosis_type,
            )
            suggested_action = self._build_permission_suggestion(
                diagnosis_type,
            )
            return DiagnosisResult(
                file_path=file_path,
                operation=operation.value,
                diagnosis=diagnosis_type,
                reason=reason,
                suggested_action=suggested_action,
                lock_result=lock_result,
                permission_result=perm_result,
            )

        # ── Step 4: No issues detected ──────────────────────────────
        return DiagnosisResult(
            file_path=file_path,
            operation=operation.value,
            diagnosis=DiagnosisType.OPERATION_ALLOWED,
            reason=(
                "The requested operation is permitted and "
                "no lock was detected."
            ),
            suggested_action="",
            lock_result=lock_result,
            permission_result=perm_result,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_lock_reason(lock_result: LockDetectionResult) -> str:
        """Build a human-readable reason string from lock results."""
        if not lock_result.processes:
            return "File is currently locked by another process."

        parts = []
        for proc in lock_result.processes:
            name = proc.process_name or "(unknown)"
            parts.append(f"{name} (PID {proc.pid})")

        if len(parts) == 1:
            return f"File is currently locked by {parts[0]}."
        return (
            "File is currently locked by: "
            + ", ".join(parts)
            + "."
        )

    @staticmethod
    def _classify_permission_failure(
        operation: FileOperation,
        perm_result: PermissionCheckResult,
    ) -> DiagnosisType:
        """Determine whether a permission failure is READ_ONLY or general.

        READ_ONLY is reported when:
            - The operation is WRITE or DELETE, AND
            - The file is readable but not writable.
        This maps directly to the common "read-only file" scenario.
        """
        if operation in (FileOperation.WRITE, FileOperation.DELETE):
            bits = perm_result.permission_bits
            if bits.get("read", False) and not bits.get("write", False):
                return DiagnosisType.READ_ONLY
        return DiagnosisType.PERMISSION_DENIED

    @staticmethod
    def _build_permission_reason(
        operation: FileOperation,
        diagnosis_type: DiagnosisType,
    ) -> str:
        """Build a human-readable reason for a permission failure."""
        op_label = operation.value.upper()

        if diagnosis_type == DiagnosisType.READ_ONLY:
            return (
                f"The file is read-only. The current user cannot "
                f"{operation.value} this file."
            )

        return (
            f"The current user does not have "
            f"{op_label} permission."
        )

    @staticmethod
    def _build_permission_suggestion(
        diagnosis_type: DiagnosisType,
    ) -> str:
        """Return an actionable suggestion for a permission failure."""
        if diagnosis_type == DiagnosisType.READ_ONLY:
            return (
                "Remove the read-only attribute or adjust the "
                "file's permissions."
            )
        return "Check the file's NTFS permissions or contact an administrator."
