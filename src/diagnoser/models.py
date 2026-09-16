"""
Shared data models for the File Operation Failure Diagnoser.

All analyzer modules return structured results using these dataclasses.
This keeps the detection logic decoupled from the GUI and diagnosis engine.
"""

from dataclasses import dataclass, field
from typing import List, Optional


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


@dataclass
class AnalyzerResult:
    """Generic result from any analyzer module.

    This base result type is used by future analyzers (permissions,
    file attributes, sync conflicts). It follows the same structured
    pattern as LockDetectionResult.

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
