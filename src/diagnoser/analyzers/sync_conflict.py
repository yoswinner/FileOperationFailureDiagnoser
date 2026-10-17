"""
Cloud-Sync Conflict Analyzer.

Inspects local operating system evidence to determine whether a target file
is associated with a supported cloud-synchronization service (Microsoft OneDrive
or Google Drive for desktop) and evaluates the likelihood of synchronization-
related file operation contention.

Supported Providers (strictly scoped):
    - Microsoft OneDrive
    - Google Drive for desktop

Evidence Levels:
    - 'none': No reliable cloud-sync folder association was discovered.
    - 'path_only': File is located within a detected sync root, but the sync client
      is not currently running and no placeholder attributes are present.
    - 'potential_contention': Multiple local signals indicate possible contention
      (e.g. sync client is running while file is in sync root, or file has cloud
      placeholder / reparse-point / offline attributes).
    - 'confirmed_lock': An active file lock held specifically by the provider's
      client process was confirmed via lock correlation.

Safety and Integrity:
    - Strictly read-only and diagnostic.
    - Never terminates, modifies, or controls client processes.
    - Never alters files, permissions, or system registry keys.
    - Operates entirely on bounded, local operating-system evidence.
"""

import os
import sys
from typing import Callable, Dict, List, Optional, Set, Tuple

import psutil

from diagnoser.analyzers.base import BaseAnalyzer
from diagnoser.models import LockDetectionResult, ProcessInfo, SyncConflictResult

# ---------------------------------------------------------------------------
# Platform check and Windows-specific imports
# ---------------------------------------------------------------------------
_IS_WINDOWS = sys.platform == "win32"

if _IS_WINDOWS:
    import ctypes
    import winreg
    from ctypes import wintypes

    try:
        _kernel32 = ctypes.windll.kernel32
    except OSError:
        _kernel32 = None
else:
    winreg = None  # type: ignore[assignment]
    _kernel32 = None

# ---------------------------------------------------------------------------
# Cloud Provider Constants
# ---------------------------------------------------------------------------
PROVIDER_ONEDRIVE = "onedrive"
PROVIDER_GOOGLE_DRIVE = "google_drive"

PROVIDER_DISPLAY_NAMES = {
    PROVIDER_ONEDRIVE: "OneDrive",
    PROVIDER_GOOGLE_DRIVE: "Google Drive",
}

# Known process names associated with supported sync clients (lowercase)
PROVIDER_PROCESS_NAMES: Dict[str, Set[str]] = {
    PROVIDER_ONEDRIVE: {"onedrive.exe", "filecoauth.exe"},
    PROVIDER_GOOGLE_DRIVE: {"googledrivefs.exe"},
}

# Windows filesystem attribute bitmasks for cloud placeholders
FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
FILE_ATTRIBUTE_OFFLINE = 0x00001000
FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS = 0x00400000
FILE_ATTRIBUTE_RECALL_ON_OPEN = 0x00040000


# ---------------------------------------------------------------------------
# Path Helper Functions
# ---------------------------------------------------------------------------

def is_subpath(child_path: str, parent_path: str) -> bool:
    """Check whether child_path is equal to or inside parent_path.

    Enforces directory boundaries and case-insensitive comparison on Windows
    paths so that sibling folders (e.g. OneDriveBackup vs OneDrive) are never
    falsely matched.

    Args:
        child_path: The target path to test.
        parent_path: The candidate root path.

    Returns:
        True if child_path is equal to or a descendant of parent_path.
    """
    try:
        norm_child = os.path.abspath(os.path.normpath(child_path)).rstrip("\\/")
        norm_parent = os.path.abspath(os.path.normpath(parent_path)).rstrip("\\/")

        c_drive, c_rest = os.path.splitdrive(norm_child)
        p_drive, p_rest = os.path.splitdrive(norm_parent)

        if c_drive.lower() != p_drive.lower():
            return False

        c_parts = [p.lower() for p in c_rest.replace("/", "\\").split("\\") if p]
        p_parts = [p.lower() for p in p_rest.replace("/", "\\").split("\\") if p]

        if len(c_parts) < len(p_parts):
            return False

        return c_parts[:len(p_parts)] == p_parts
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Correlation Helper
# ---------------------------------------------------------------------------

def correlate_sync_lock(
    sync_result: SyncConflictResult,
    lock_result: Optional[LockDetectionResult],
) -> SyncConflictResult:
    """Correlate a SyncConflictResult with a real LockDetectionResult.

    Elevates evidence_level to 'confirmed_lock' ONLY when an active lock
    is held by a process that reliably matches the supported sync provider.
    If the lock is held by an unrelated application (e.g. notepad.exe),
    evidence is NOT attributed to the sync provider.

    Args:
        sync_result: The result from SyncConflictAnalyzer.
        lock_result: The result from ProcessLockAnalyzer.

    Returns:
        An updated SyncConflictResult reflecting the correlation findings.
    """
    if not lock_result or not lock_result.is_locked or not lock_result.processes:
        return sync_result

    # Determine candidate sync process names
    provider = sync_result.provider.lower()
    candidate_procs = PROVIDER_PROCESS_NAMES.get(provider, set())

    matching_proc: Optional[ProcessInfo] = None
    inferred_provider = sync_result.provider

    if candidate_procs:
        for proc in lock_result.processes:
            p_name = (proc.process_name or "").lower()
            if p_name in candidate_procs:
                matching_proc = proc
                break
    else:
        # Check if any locking process belongs to any supported provider
        for prov_key, procs in PROVIDER_PROCESS_NAMES.items():
            for proc in lock_result.processes:
                p_name = (proc.process_name or "").lower()
                if p_name in procs:
                    matching_proc = proc
                    inferred_provider = prov_key
                    break
            if matching_proc:
                break

    if matching_proc:
        prov_title = PROVIDER_DISPLAY_NAMES.get(inferred_provider, "Cloud Sync")
        return SyncConflictResult(
            file_path=sync_result.file_path,
            is_synced=sync_result.is_synced if sync_result.is_synced is not None else True,
            provider=inferred_provider,
            sync_root=sync_result.sync_root,
            client_running=True,
            evidence_level="confirmed_lock",
            is_conflict=True,
            locking_process=matching_proc,
            details=(
                f"Confirmed cloud sync conflict: {matching_proc.process_name} "
                f"(PID {matching_proc.pid}) from {prov_title} currently holds an active lock on this file."
            ),
            error=sync_result.error,
            detection_method=sync_result.detection_method or "local_sync_detection",
        )

    # An active lock exists, but held by an unrelated process
    locking_names = ", ".join(
        f"{p.process_name or 'unknown'} (PID {p.pid})" for p in lock_result.processes
    )
    details = sync_result.details
    note = f" Note: File is locked by non-sync application: {locking_names}."
    if details:
        details += note
    else:
        details = note.strip()

    return SyncConflictResult(
        file_path=sync_result.file_path,
        is_synced=sync_result.is_synced,
        provider=sync_result.provider,
        sync_root=sync_result.sync_root,
        client_running=sync_result.client_running,
        evidence_level=sync_result.evidence_level,
        is_conflict=False,
        locking_process=None,
        details=details,
        error=sync_result.error,
        detection_method=sync_result.detection_method,
    )


# ---------------------------------------------------------------------------
# SyncConflictAnalyzer
# ---------------------------------------------------------------------------

class SyncConflictAnalyzer(BaseAnalyzer):
    """Detects synchronization-related file conflicts.

    Inspects real local evidence for OneDrive and Google Drive for desktop:
    - Bounded sync root discovery via environment variables and registry.
    - Running client process discovery via psutil.
    - Filesystem reparse-point and offline placeholder attributes.
    - Conservative evidence levels: 'none', 'path_only', 'potential_contention',
      and 'confirmed_lock'.

    Safety:
        Strictly read-only and diagnostic. Never modifies files, registry,
        or processes.
    """

    def __init__(
        self,
        roots_override: Optional[Dict[str, List[str]]] = None,
        process_checker: Optional[Callable[[str], Tuple[bool, List[ProcessInfo]]]] = None,
        attribute_checker: Optional[Callable[[str], Tuple[bool, bool]]] = None,
    ):
        """Initialize the SyncConflictAnalyzer.

        Args:
            roots_override: Optional mapping of provider ('onedrive', 'google_drive')
                            to a list of root path strings. Used for deterministic testing.
            process_checker: Optional callable returning (client_running, list_of_procs)
                             for a provider name. Used for testing.
            attribute_checker: Optional callable returning (is_reparse, is_offline)
                               for a file path. Used for testing.
        """
        self._roots_override = roots_override
        self._process_checker = process_checker
        self._attribute_checker = attribute_checker

    def analyze(self, file_path: str) -> SyncConflictResult:
        """Analyse sync status and conflict evidence for the specified file.

        Args:
            file_path: Path to the target file.

        Returns:
            SyncConflictResult detailing cloud-sync association and evidence.
        """
        # Validate path
        try:
            norm_path = self.validate_path(file_path)
        except Exception as exc:
            return SyncConflictResult(
                file_path=str(file_path),
                is_synced=None,
                evidence_level="none",
                details=f"Invalid file path: {exc}",
                error=f"Invalid file path: {exc}",
                detection_method="error",
            )

        if not os.path.exists(norm_path):
            return SyncConflictResult(
                file_path=norm_path,
                is_synced=None,
                evidence_level="none",
                details="Cannot inspect sync status: path does not exist or is inaccessible.",
                error="The specified file does not exist or is inaccessible.",
                detection_method="error",
            )

        if os.path.isdir(norm_path):
            return SyncConflictResult(
                file_path=norm_path,
                is_synced=None,
                evidence_level="none",
                details="The path specifies a directory, not a file.",
                error="The path specifies a directory, not a file.",
                detection_method="error",
            )

        # 1. Discover candidate roots for supported providers
        provider_roots = self._get_all_roots()

        # 2. Match against candidate roots (find deepest / most specific match)
        matched_provider: str = ""
        matched_root: str = ""

        for provider, roots in provider_roots.items():
            for root in roots:
                if is_subpath(norm_path, root):
                    # Prefer the deepest root if multiple match
                    if not matched_root or len(root) > len(matched_root):
                        matched_provider = provider
                        matched_root = root

        # If not inside any known sync root
        if not matched_provider or not matched_root:
            method = "local_sync_detection" if _IS_WINDOWS else "unsupported_platform"
            return SyncConflictResult(
                file_path=norm_path,
                is_synced=False,
                provider="",
                sync_root="",
                client_running=False,
                evidence_level="none",
                is_conflict=False,
                locking_process=None,
                details=(
                    "File is not located within any detected cloud-sync folder "
                    "(OneDrive or Google Drive). Note: discovery is bounded to "
                    "local environment and registry configuration and may be incomplete."
                ),
                error=None,
                detection_method=method,
            )

        # 3. Check if provider client process is currently running
        client_running, running_procs = self._is_client_running(matched_provider)

        # 4. Check for reparse-point and offline placeholder attributes
        is_reparse, is_offline = self._check_reparse_or_offline(norm_path)

        # 5. Determine evidence level conservatively
        provider_title = PROVIDER_DISPLAY_NAMES.get(matched_provider, matched_provider.capitalize())

        if not client_running and not (is_reparse or is_offline):
            evidence_level = "path_only"
            details = (
                f"File is located within a {provider_title} folder ({matched_root}), "
                f"but the {provider_title} client is not currently running. "
                "No active sync contention detected."
            )
        elif not client_running and (is_reparse or is_offline):
            evidence_level = "potential_contention"
            attrs = []
            if is_reparse:
                attrs.append("reparse point")
            if is_offline:
                attrs.append("offline")
            attr_str = "/".join(attrs)
            details = (
                f"File is located within a {provider_title} folder ({matched_root}) "
                f"and has cloud placeholder attributes ({attr_str}), but the {provider_title} "
                "client is not currently running. File content may not be available locally."
            )
        elif client_running and not (is_reparse or is_offline):
            evidence_level = "potential_contention"
            details = (
                f"File is located within an active {provider_title} sync folder ({matched_root}) "
                f"and the {provider_title} client process is running. Background synchronization "
                "may cause transient access contention, but no file lock is confirmed."
            )
        else:
            # client_running and (is_reparse or is_offline)
            evidence_level = "potential_contention"
            attrs = []
            if is_reparse:
                attrs.append("reparse point")
            if is_offline:
                attrs.append("offline")
            attr_str = "/".join(attrs)
            details = (
                f"File is located within an active {provider_title} sync folder ({matched_root}), "
                f"the {provider_title} client process is running, and the file has cloud placeholder "
                f"attributes ({attr_str}). Active synchronization contention is possible."
            )

        return SyncConflictResult(
            file_path=norm_path,
            is_synced=True,
            provider=matched_provider,
            sync_root=matched_root,
            client_running=client_running,
            evidence_level=evidence_level,
            is_conflict=False,
            locking_process=None,
            details=details,
            error=None,
            detection_method="local_sync_detection",
        )

    @staticmethod
    def correlate_lock(
        sync_result: SyncConflictResult,
        lock_result: Optional[LockDetectionResult],
    ) -> SyncConflictResult:
        """Convenience method delegating to correlate_sync_lock."""
        return correlate_sync_lock(sync_result, lock_result)

    # ------------------------------------------------------------------
    # Root Discovery Helpers
    # ------------------------------------------------------------------

    def _get_all_roots(self) -> Dict[str, List[str]]:
        """Return discovered candidate roots for all supported providers."""
        if self._roots_override is not None:
            return {
                prov: [os.path.abspath(os.path.normpath(r)) for r in roots]
                for prov, roots in self._roots_override.items()
            }

        return {
            PROVIDER_ONEDRIVE: self._get_onedrive_roots(),
            PROVIDER_GOOGLE_DRIVE: self._get_google_drive_roots(),
        }

    def _get_onedrive_roots(self) -> List[str]:
        """Discover Microsoft OneDrive local sync roots from environment and registry."""
        roots: Set[str] = set()

        # Check environment variables
        for env_var in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
            val = os.environ.get(env_var)
            if val and os.path.exists(val):
                roots.add(os.path.abspath(os.path.normpath(val)))

        # On Windows, inspect registry safely
        if _IS_WINDOWS and winreg is not None:
            # 1. HKCU\Software\Microsoft\OneDrive\Accounts\*
            try:
                with winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER, r"Software\Microsoft\OneDrive\Accounts"
                ) as accounts_key:
                    idx = 0
                    while True:
                        try:
                            subkey_name = winreg.EnumKey(accounts_key, idx)
                            with winreg.OpenKey(accounts_key, subkey_name) as subkey:
                                try:
                                    folder, _ = winreg.QueryValueEx(subkey, "UserFolder")
                                    if folder and os.path.exists(folder):
                                        roots.add(os.path.abspath(os.path.normpath(folder)))
                                except (OSError, FileNotFoundError):
                                    pass
                            idx += 1
                        except OSError:
                            break
            except (OSError, FileNotFoundError, PermissionError):
                pass

            # 2. HKCU\Software\Microsoft\OneDrive -> UserFolder
            try:
                with winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER, r"Software\Microsoft\OneDrive"
                ) as onedrive_key:
                    try:
                        folder, _ = winreg.QueryValueEx(onedrive_key, "UserFolder")
                        if folder and os.path.exists(folder):
                            roots.add(os.path.abspath(os.path.normpath(folder)))
                    except (OSError, FileNotFoundError):
                        pass
            except (OSError, FileNotFoundError, PermissionError):
                pass

        return sorted(list(roots))

    def _get_google_drive_roots(self) -> List[str]:
        """Discover Google Drive for desktop mount points and roots."""
        roots: Set[str] = set()

        # 1. On Windows, inspect registry for DriveFS MountPoint
        if _IS_WINDOWS and winreg is not None:
            for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                try:
                    with winreg.OpenKey(hive, r"Software\Google\DriveFS") as key:
                        for val_name in ("MountPoint", "DefaultMountPoint"):
                            try:
                                val, _ = winreg.QueryValueEx(key, val_name)
                                if val:
                                    # Val could be single drive letter like 'G' or path 'G:\'
                                    if len(val) == 1 and val.isalpha():
                                        val = f"{val}:\\"
                                    elif len(val) == 2 and val[1] == ":":
                                        val = f"{val}\\"
                                    if os.path.exists(val):
                                        roots.add(os.path.abspath(os.path.normpath(val)))
                            except (OSError, FileNotFoundError):
                                pass
                except (OSError, FileNotFoundError, PermissionError):
                    pass

        # 2. Check disk partitions via psutil for DriveFS filesystem or mount
        try:
            for part in psutil.disk_partitions(all=True):
                try:
                    fstype = getattr(part, "fstype", "").lower()
                    opts = getattr(part, "opts", "").lower()
                    mount = getattr(part, "mountpoint", "")
                    if "drivefs" in fstype or "drivefs" in opts:
                        if mount and os.path.exists(mount):
                            roots.add(os.path.abspath(os.path.normpath(mount)))
                    elif _IS_WINDOWS and _kernel32 and mount:
                        # Check volume label via GetVolumeInformationW
                        vol_buf = ctypes.create_unicode_buffer(260)
                        fs_buf = ctypes.create_unicode_buffer(260)
                        res = _kernel32.GetVolumeInformationW(
                            mount, vol_buf, 260, None, None, None, fs_buf, 260
                        )
                        if res:
                            vol_label = vol_buf.value.lower()
                            fs_label = fs_buf.value.lower()
                            if "google drive" in vol_label or "drivefs" in fs_label:
                                if os.path.exists(mount):
                                    roots.add(os.path.abspath(os.path.normpath(mount)))
                except (OSError, PermissionError):
                    continue
        except Exception:
            pass

        return sorted(list(roots))

    # ------------------------------------------------------------------
    # Process and Attribute Inspection
    # ------------------------------------------------------------------

    def _is_client_running(self, provider: str) -> Tuple[bool, List[ProcessInfo]]:
        """Check if client processes for the specified provider are running."""
        if self._process_checker is not None:
            return self._process_checker(provider)

        target_names = PROVIDER_PROCESS_NAMES.get(provider.lower(), set())
        if not target_names:
            return False, []

        found: List[ProcessInfo] = []
        try:
            for proc in psutil.process_iter(["pid", "name", "exe"]):
                try:
                    p_name = (proc.info.get("name") or "").lower()
                    if p_name in target_names:
                        found.append(
                            ProcessInfo(
                                process_name=proc.info.get("name") or p_name,
                                pid=proc.info.get("pid") or proc.pid,
                                executable_path=proc.info.get("exe") or "",
                            )
                        )
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
                except Exception:
                    continue
        except Exception:
            pass

        return len(found) > 0, found

    def _check_reparse_or_offline(self, file_path: str) -> Tuple[bool, bool]:
        """Check whether the file has reparse-point or offline placeholder attributes."""
        if self._attribute_checker is not None:
            return self._attribute_checker(file_path)

        if not os.path.exists(file_path):
            return False, False

        # Attempt to inspect st_file_attributes on stat result (Windows)
        try:
            st = os.stat(file_path)
            attrs = getattr(st, "st_file_attributes", None)
            if attrs is not None:
                is_reparse = bool(attrs & FILE_ATTRIBUTE_REPARSE_POINT)
                is_offline = bool(
                    attrs & (FILE_ATTRIBUTE_OFFLINE | FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS)
                )
                return is_reparse, is_offline
        except OSError:
            pass

        # Fallback to GetFileAttributesW on Windows if available
        if _IS_WINDOWS and _kernel32:
            try:
                raw = _kernel32.GetFileAttributesW(file_path)
                if raw != 0xFFFFFFFF:
                    is_reparse = bool(raw & FILE_ATTRIBUTE_REPARSE_POINT)
                    is_offline = bool(
                        raw & (FILE_ATTRIBUTE_OFFLINE | FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS)
                    )
                    return is_reparse, is_offline
            except Exception:
                pass

        return False, False
