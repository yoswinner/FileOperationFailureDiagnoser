"""
Process / File-Lock Detection Analyzer.

Detects which processes currently hold a file open using the
Windows Restart Manager API (Rstrtmgr.dll).

The Restart Manager is the official, documented Windows mechanism
for identifying applications that are using specific file resources.
It is the same API that Windows uses internally when it displays the
"This file is in use by another program" dialog.

API workflow:
    1. RmStartSession   — create a Restart Manager session
    2. RmRegisterResources — register the target file path
    3. RmGetList         — retrieve the list of RM_PROCESS_INFO structs
                           for processes currently using that resource
    4. RmEndSession      — clean up the session

psutil is used only for enriching process information (e.g. resolving
the full executable path from a PID).  It is NOT used as a lock-
detection mechanism.

Platform note:
    All Windows-specific code is isolated inside the
    _detect_locks_restart_manager() method.  On non-Windows platforms,
    analyze() returns a clear 'unsupported_platform' result so that the
    rest of the codebase (models, tests, GUI) can be developed and
    tested on macOS/Linux.

Reference:
    https://learn.microsoft.com/windows/win32/api/restartmanager/nf-restartmanager-rmgetlist
    https://learn.microsoft.com/windows/win32/api/restartmanager/ns-restartmanager-rm_process_info
"""

import os
import sys
from typing import List

from diagnoser.analyzers.base import BaseAnalyzer
from diagnoser.models import LockDetectionResult, ProcessInfo

# ---------------------------------------------------------------------------
# Windows-specific imports — guarded behind a platform check
# ---------------------------------------------------------------------------
_IS_WINDOWS = sys.platform == "win32"

if _IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    # -----------------------------------------------------------------------
    # Restart Manager constants (from restartmanager.h)
    # -----------------------------------------------------------------------
    CCH_RM_MAX_APP_NAME = 255
    CCH_RM_MAX_SVC_NAME = 63
    # Maximum session key length (characters)
    CCH_RM_SESSION_KEY = 64

    # RmGetList return codes we handle
    ERROR_SUCCESS = 0
    ERROR_MORE_DATA = 234

    # -----------------------------------------------------------------------
    # ctypes structure definitions matching the Windows C structs
    # -----------------------------------------------------------------------
    class RM_UNIQUE_PROCESS(ctypes.Structure):
        """Maps to the Windows RM_UNIQUE_PROCESS structure.

        Fields:
            dwProcessId  — the process ID.
            ProcessStartTime — FILETIME when the process started.
                Together with the PID this uniquely identifies a process
                instance (since PIDs can be recycled).
        """
        _fields_ = [
            ("dwProcessId", wintypes.DWORD),
            ("ProcessStartTime", wintypes.FILETIME),
        ]

    class RM_PROCESS_INFO(ctypes.Structure):
        """Maps to the Windows RM_PROCESS_INFO structure.

        This is the struct returned by RmGetList for each process that
        is currently using a registered resource (file).

        Fields:
            Process             — RM_UNIQUE_PROCESS (PID + start time)
            strAppName          — human-friendly application name
            strServiceShortName — service short name (empty if not a service)
            ApplicationType     — RM_APP_TYPE enum value
            AppStatus           — bitmask of RM_APP_STATUS
            TSSessionId         — Terminal Services session ID
            bRestartable        — whether the app can be restarted by RM
        """
        _fields_ = [
            ("Process", RM_UNIQUE_PROCESS),
            ("strAppName", ctypes.c_wchar * (CCH_RM_MAX_APP_NAME + 1)),
            ("strServiceShortName", ctypes.c_wchar * (CCH_RM_MAX_SVC_NAME + 1)),
            ("ApplicationType", ctypes.c_uint),
            ("AppStatus", wintypes.ULONG),
            ("TSSessionId", wintypes.ULONG),
            ("bRestartable", wintypes.BOOL),
        ]

    # Load the Restart Manager DLL
    try:
        _rstrtmgr = ctypes.windll.rstrtmgr
    except OSError:
        _rstrtmgr = None


class ProcessLockAnalyzer(BaseAnalyzer):
    """Detects processes holding a file open via the Windows Restart Manager.

    Usage:
        analyzer = ProcessLockAnalyzer()
        result = analyzer.analyze(r"C:\\path\\to\\file.txt")
        if result.is_locked:
            for proc in result.processes:
                print(f"{proc.process_name} (PID {proc.pid})")
    """

    def analyze(self, file_path: str) -> LockDetectionResult:
        """Analyse whether the file is locked by another process.

        Handles five cases gracefully:
            1. File does not exist           → error, is_locked=False
            2. File exists and is not locked  → is_locked=False
            3. File is used by a process      → is_locked=True, processes filled
            4. Insufficient permissions       → error with details
            5. Unexpected API errors          → error with details

        Args:
            file_path: Path to the file to check.

        Returns:
            LockDetectionResult with structured diagnostic data.
        """
        file_path = self.validate_path(file_path)

        # ----- Case 1: file does not exist -----
        if not os.path.exists(file_path):
            return LockDetectionResult(
                file_path=file_path,
                is_locked=False,
                error=f"File does not exist: {file_path}",
                detection_method="error",
            )

        # Ensure it is a file, not a directory
        if not os.path.isfile(file_path):
            return LockDetectionResult(
                file_path=file_path,
                is_locked=False,
                error=f"Path is a directory, not a file: {file_path}",
                detection_method="error",
            )

        # ----- Case 4 (partial): basic read-access check -----
        if not os.access(file_path, os.R_OK):
            return LockDetectionResult(
                file_path=file_path,
                is_locked=False,
                error=f"Insufficient permissions to read: {file_path}",
                detection_method="error",
            )

        # ----- Platform gate -----
        if not _IS_WINDOWS:
            return LockDetectionResult(
                file_path=file_path,
                is_locked=False,
                error=(
                    "Lock detection requires Windows. "
                    "The Restart Manager API is not available on this platform."
                ),
                detection_method="unsupported_platform",
            )

        # ----- Cases 2, 3, 4, 5: Windows Restart Manager detection -----
        return self._detect_locks_restart_manager(file_path)

    # ------------------------------------------------------------------
    # Windows-only implementation
    # ------------------------------------------------------------------
    def _detect_locks_restart_manager(self, file_path: str) -> LockDetectionResult:
        """Query the Windows Restart Manager for processes using *file_path*.

        This method is only called on Windows.  It follows the official
        API workflow:
            RmStartSession → RmRegisterResources → RmGetList → RmEndSession

        RmGetList returns only processes that the Restart Manager has
        determined are *currently using* the registered resource.  A
        process merely being alive does NOT cause it to appear in the
        list — the association is based on actual file-resource usage.

        Returns:
            LockDetectionResult populated from the API response.
        """
        if _rstrtmgr is None:
            return LockDetectionResult(
                file_path=file_path,
                is_locked=False,
                error="Restart Manager DLL (Rstrtmgr.dll) could not be loaded.",
                detection_method="error",
            )

        session_handle = wintypes.DWORD()
        session_key = ctypes.create_unicode_buffer(CCH_RM_SESSION_KEY + 1)

        # --- Step 1: Start a Restart Manager session ---
        ret = _rstrtmgr.RmStartSession(
            ctypes.byref(session_handle), 0, session_key
        )
        if ret != ERROR_SUCCESS:
            return LockDetectionResult(
                file_path=file_path,
                is_locked=False,
                error=f"RmStartSession failed with error code {ret}.",
                detection_method="error",
            )

        try:
            # --- Step 2: Register the file as a resource ---
            file_path_ptr = ctypes.c_wchar_p(file_path)
            files_array = (ctypes.c_wchar_p * 1)(file_path_ptr)
            ret = _rstrtmgr.RmRegisterResources(
                session_handle,
                1,              # nFiles
                files_array,
                0,              # nApplications
                None,           # rgApplications
                0,              # nServices
                None,           # rgsServiceNames
            )
            if ret != ERROR_SUCCESS:
                return LockDetectionResult(
                    file_path=file_path,
                    is_locked=False,
                    error=f"RmRegisterResources failed with error code {ret}.",
                    detection_method="error",
                )

            # --- Step 3: Get the list of processes using this file ---
            pn_proc_info_needed = wintypes.UINT(0)
            pn_proc_info = wintypes.UINT(0)
            reboot_reasons = wintypes.DWORD(0)

            # First call: ask how large the buffer needs to be
            ret = _rstrtmgr.RmGetList(
                session_handle,
                ctypes.byref(pn_proc_info_needed),
                ctypes.byref(pn_proc_info),
                None,
                ctypes.byref(reboot_reasons),
            )

            if ret == ERROR_SUCCESS and pn_proc_info_needed.value == 0:
                # Case 2: no processes are using this file
                return LockDetectionResult(
                    file_path=file_path,
                    is_locked=False,
                    detection_method="restart_manager",
                )

            if ret != ERROR_MORE_DATA:
                # Unexpected error (e.g. access denied)
                return LockDetectionResult(
                    file_path=file_path,
                    is_locked=False,
                    error=f"RmGetList failed with error code {ret}.",
                    detection_method="error",
                )

            # Allocate a buffer large enough for all results
            n_procs = pn_proc_info_needed.value
            pn_proc_info = wintypes.UINT(n_procs)
            rm_infos = (RM_PROCESS_INFO * n_procs)()

            ret = _rstrtmgr.RmGetList(
                session_handle,
                ctypes.byref(pn_proc_info_needed),
                ctypes.byref(pn_proc_info),
                rm_infos,
                ctypes.byref(reboot_reasons),
            )

            if ret != ERROR_SUCCESS:
                return LockDetectionResult(
                    file_path=file_path,
                    is_locked=False,
                    error=f"RmGetList (second call) failed with error code {ret}.",
                    detection_method="error",
                )

            # --- Build the result from the RM_PROCESS_INFO array ---
            processes = self._extract_process_info(rm_infos, pn_proc_info.value)

            return LockDetectionResult(
                file_path=file_path,
                is_locked=len(processes) > 0,
                processes=processes,
                detection_method="restart_manager",
            )

        finally:
            # --- Step 4: Always clean up the session ---
            _rstrtmgr.RmEndSession(session_handle)

    @staticmethod
    def _extract_process_info(
        rm_infos, count: int
    ) -> List[ProcessInfo]:
        """Convert RM_PROCESS_INFO array entries to ProcessInfo objects.

        Uses psutil to enrich each entry with the full executable path,
        since the Restart Manager only provides the PID and app name.
        If psutil cannot retrieve the path (e.g. access denied or the
        process exited between detection and enrichment), the path is
        left empty.

        Args:
            rm_infos: ctypes array of RM_PROCESS_INFO structures.
            count: Number of valid entries in the array.

        Returns:
            List of ProcessInfo dataclasses.
        """
        results: List[ProcessInfo] = []

        for i in range(count):
            pid = rm_infos[i].Process.dwProcessId
            app_name = rm_infos[i].strAppName or ""

            # Enrich with the full executable path via psutil
            exe_path = ""
            try:
                import psutil
                proc = psutil.Process(pid)
                exe_path = proc.exe() or ""
            except Exception:
                # Process may have exited, or access denied — leave blank
                pass

            results.append(ProcessInfo(
                process_name=app_name,
                pid=pid,
                executable_path=exe_path,
            ))

        return results
