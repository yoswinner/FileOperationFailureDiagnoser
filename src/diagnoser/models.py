"""
Shared data models for the File Operation Failure Diagnoser.

All analyzer modules return structured results using these dataclasses.
This keeps the detection logic decoupled from the GUI and diagnosis engine.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


# ======================================================================
# Enumerations
# ======================================================================

class FileOperation(Enum):
    """File operations that can be checked for permission.

    Each value maps to a human-readable label used in diagnostics.
    """
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    DELETE = "delete"


# ======================================================================
# Process / Lock Detection models (Milestone 1)
# ======================================================================

@dataclass
class ProcessInfo:
    """Information about a process that is using a file.

    Attributes:
        process_name: The name of the process (e.g. 'notepad.exe').
        pid: The process ID.
        executable_path: Full path to the process executable, if available.
    """
    process_name: str
    pid: int
    executable_path: str = ""


@dataclass
class LockDetectionResult:
    """Result of a file-lock detection analysis.

    This is the structured output from the ProcessLockAnalyzer.
    The diagnosis engine and GUI consume this data — they never call
    Windows APIs directly.

    Attributes:
        file_path: The absolute path of the file that was analysed.
        is_locked: True if the file is currently held open by one or more
                   processes, as reported by the detection method.
        processes: List of ProcessInfo objects for each process using the
                   file. Empty if the file is not locked or if detection
                   failed.
        error: A human-readable error message if something went wrong
               during detection (e.g. file not found, permission denied,
               API failure). None if detection completed without errors.
        detection_method: The method used for detection, e.g.
                          'restart_manager', 'unsupported_platform',
                          or 'error'.
    """
    file_path: str
    is_locked: bool = False
    processes: List[ProcessInfo] = field(default_factory=list)
    error: Optional[str] = None
    detection_method: str = ""


# ======================================================================
# Permission / Ownership models (Milestone 2)
# ======================================================================

@dataclass
class PermissionCheckResult:
    """Result of a permission/ownership analysis.

    This is the structured output from the PermissionAnalyzer.

    Attributes:
        file_path: The absolute path of the file that was analysed.
        operation: The file operation that was checked (READ, WRITE, etc.).
        permitted: True if the current user has the requested access.
        owner: The file owner in 'DOMAIN\\User' format (Windows) or
               username (POSIX). Empty string if not determined.
        current_user: The name of the user running this process.
        details: A human-readable explanation of the finding.
        permission_bits: A dictionary of permission flags and their
                         boolean values, e.g. {'read': True, 'write': False}.
        error: A human-readable error message if analysis failed.
               None if analysis completed without errors.
        detection_method: The method used for detection, e.g.
                          'os_access', 'windows_acl', or 'error'.
    """
    file_path: str
    operation: str = ""
    permitted: bool = False
    owner: str = ""
    current_user: str = ""
    details: str = ""
    permission_bits: Dict[str, bool] = field(default_factory=dict)
    error: Optional[str] = None
    detection_method: str = ""


# ======================================================================
# File Attribute models (Review 3 - Milestone 5)
# ======================================================================

@dataclass
class FileAttributeResult:
    """Result of a file-attribute analysis.

    This is the structured output from the FileAttributeAnalyzer.

    Attributes:
        file_path: The absolute path of the file that was analysed.
        is_readonly: True if the read-only attribute is set; False if not;
                     None if undetermined or unsupported on this platform.
        is_hidden: True if the hidden attribute is set; False if not;
                   None if undetermined or unsupported on this platform.
        is_system: True if marked as a system file; False if not;
                   None if undetermined or unsupported on this platform.
        is_archive: True if the archive attribute is set; False if not;
                    None if undetermined or unsupported on this platform.
        is_reparse_point: True if the file is a reparse point (e.g. symlink,
                          junction, or cloud placeholder); False if not;
                          None if undetermined or unsupported on this platform.
        is_offline: True if the file data is not immediately available locally
                    (e.g. cloud placeholder / HSM); False if not;
                    None if undetermined or unsupported on this platform.
        raw_attributes: The raw integer bitmask of attributes, if available.
        attributes_list: List of human-readable attribute names detected
                         (e.g. ['READONLY', 'ARCHIVE']).
        error: A human-readable error message if something went wrong
               during detection. None if detection completed without errors.
        detection_method: Method used ('windows_stat', 'windows_api',
                          'posix_stat', 'unsupported_platform', or 'error').
    """
    file_path: str
    is_readonly: Optional[bool] = None
    is_hidden: Optional[bool] = None
    is_system: Optional[bool] = None
    is_archive: Optional[bool] = None
    is_reparse_point: Optional[bool] = None
    is_offline: Optional[bool] = None
    raw_attributes: Optional[int] = None
    attributes_list: List[str] = field(default_factory=list)
    error: Optional[str] = None
    detection_method: str = ""


# ======================================================================
# Cloud-Sync models (Review 3 - Milestone 6)
# ======================================================================

@dataclass
class SyncConflictResult:
    """Result of a cloud-synchronisation conflict analysis.

    Designed for OneDrive and Google Drive local client detection.

    Attributes:
        file_path: The absolute path of the file that was analysed.
        is_synced: True if the file resides inside a detected cloud-sync folder;
                   False if not; None if undetermined.
        provider: Name of the cloud provider ('onedrive', 'google_drive',
                  or '' if none).
        sync_root: The root local directory of the sync provider.
        client_running: True if the provider's local background process
                        (e.g. OneDrive.exe, GoogleDriveFS.exe) is currently running.
        evidence_level: Level of confidence ('none', 'path_only',
                        'potential_contention', 'confirmed_lock').
        is_conflict: True if there is evidence of an active synchronization
                     lock or conflict affecting the file.
        locking_process: ProcessInfo of the sync process holding the file lock,
                         if confirmed by lock analysis.
        details: Human-readable explanation of sync status and evidence.
        error: Human-readable error message if detection encountered an issue.
        detection_method: Method used ('local_sync_detection',
                          'unsupported_platform', or 'error').
    """
    file_path: str
    is_synced: Optional[bool] = None
    provider: str = ""
    sync_root: str = ""
    client_running: bool = False
    evidence_level: str = "none"
    is_conflict: bool = False
    locking_process: Optional[ProcessInfo] = None
    details: str = ""
    error: Optional[str] = None
    detection_method: str = ""


# ======================================================================
# Diagnosis Engine models (Milestone 3)
# ======================================================================

class DiagnosisType(Enum):
    """Classification of the primary reason a file operation would fail.

    The diagnosis engine evaluates analyzers in a fixed priority order
    and assigns exactly one DiagnosisType per diagnosis run.
    """
    FILE_NOT_FOUND = "file_not_found"
    FILE_LOCKED = "file_locked"
    PERMISSION_DENIED = "permission_denied"
    READ_ONLY = "read_only"
    OPERATION_ALLOWED = "operation_allowed"
    UNKNOWN_ERROR = "unknown_error"
    SYNC_CONFLICT = "sync_conflict"


@dataclass
class DiagnosisResult:
    """Structured output from the diagnosis engine.

    Contains enough information for a CLI or GUI to display a
    human-readable summary of why a file operation would fail.

    Attributes:
        file_path: The absolute path of the file that was diagnosed.
        operation: The requested file operation (e.g. 'write').
        diagnosis: The primary DiagnosisType classification.
        reason: A human-readable explanation of the diagnosis.
        suggested_action: An actionable recommendation for the user.
        lock_result: The raw LockDetectionResult, if a lock check
                     was performed.  None otherwise.
        permission_result: The raw PermissionCheckResult, if a
                           permission check was performed.  None otherwise.
        attribute_result: The raw FileAttributeResult, if an attribute check
                          was performed.  None otherwise.
        sync_result: The raw SyncConflictResult, if a sync check
                     was performed.  None otherwise.
    """
    file_path: str
    operation: str = ""
    diagnosis: DiagnosisType = DiagnosisType.UNKNOWN_ERROR
    reason: str = ""
    suggested_action: str = ""
    lock_result: Optional[LockDetectionResult] = None
    permission_result: Optional[PermissionCheckResult] = None
    attribute_result: Optional[FileAttributeResult] = None
    sync_result: Optional[SyncConflictResult] = None


# ======================================================================
# Generic Analyzer Result (used by future modules)
# ======================================================================

@dataclass
class AnalyzerResult:
    """Generic result from any analyzer module.

    This base result type is used by future analyzers (file attributes,
    sync conflicts). It follows the same structured pattern as
    LockDetectionResult and PermissionCheckResult.

    Attributes:
        detected: Whether an issue was detected.
        issue: Short description of the issue (e.g. 'File is read-only').
        details: Longer explanation with context.
        severity: One of 'none', 'info', 'warning', 'error'.
        evidence: Supporting data points for the diagnosis.
        analyzer_name: Name of the analyzer that produced this result.
    """
    detected: bool = False
    issue: str = ""
    details: str = ""
    severity: str = "none"
    evidence: List[str] = field(default_factory=list)
    analyzer_name: str = ""
