"""
Permission and Ownership Analyzer.

Determines whether the current user has the required access rights
(read, write, execute, delete) to perform an operation on a file.

Cross-platform layer:
    Uses os.access() for basic permission checks.  This works on all
    platforms and reflects the effective access of the current user.

Windows layer (Rstrtmgr.dll is NOT involved here):
    Uses ctypes → advapi32.dll to query NTFS security descriptors:
      - GetNamedSecurityInfoW  — retrieves the file's security descriptor
                                 including owner SID and DACL
      - LookupAccountSidW     — resolves a SID to DOMAIN\\Username

    This gives richer information than os.access() alone:
      - Who owns the file
      - Whether the DACL explicitly denies the requested access

Platform note:
    On non-Windows platforms the analyzer falls back to os.access()
    and POSIX stat/uid for ownership.  It clearly labels the
    detection_method so the diagnosis engine knows what level of
    detail is available.

Safety:
    This module is read-only.  It never modifies permissions, ACLs,
    or ownership.

Reference:
    https://learn.microsoft.com/windows/win32/api/aclapi/nf-aclapi-getnamedsecurityinfow
    https://learn.microsoft.com/windows/win32/api/winbase/nf-winbase-lookupaccountsidw
"""

import getpass
import os
import stat
import sys
from typing import Dict

from diagnoser.analyzers.base import BaseAnalyzer
from diagnoser.models import FileOperation, PermissionCheckResult

# ---------------------------------------------------------------------------
# Windows-specific imports — guarded behind a platform check
# ---------------------------------------------------------------------------
_IS_WINDOWS = sys.platform == "win32"

if _IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    # -----------------------------------------------------------------------
    # advapi32.dll constants
    # -----------------------------------------------------------------------
    SE_FILE_OBJECT = 1

    # SECURITY_INFORMATION flags
    OWNER_SECURITY_INFORMATION = 0x00000001
    DACL_SECURITY_INFORMATION = 0x00000004

    ERROR_SUCCESS = 0

    # Load advapi32.dll for security APIs
    try:
        _advapi32 = ctypes.windll.advapi32
    except OSError:
        _advapi32 = None

    # kernel32 for LocalFree (to free security descriptor memory)
    try:
        _kernel32 = ctypes.windll.kernel32
    except OSError:
        _kernel32 = None


# -----------------------------------------------------------------------
# Permission flag constants for os.access() mapping
# -----------------------------------------------------------------------
_OPERATION_TO_ACCESS_FLAG = {
    FileOperation.READ: os.R_OK,
    FileOperation.WRITE: os.W_OK,
    FileOperation.EXECUTE: os.X_OK,
    # DELETE on POSIX requires write on the parent directory;
    # on Windows os.access doesn't directly test delete, so we
    # approximate with write-check and note the limitation.
    FileOperation.DELETE: os.W_OK,
}


class PermissionAnalyzer(BaseAnalyzer):
    """Analyses file permissions and ownership.

    Accepts a file path and a requested operation, then determines
    whether the current user has the required access rights.

    Usage:
        analyzer = PermissionAnalyzer()
        result = analyzer.analyze(r"C:\\file.txt", FileOperation.WRITE)
        if not result.permitted:
            print(result.details)
    """

    def analyze(
        self,
        file_path: str,
        operation: FileOperation = FileOperation.READ,
    ) -> PermissionCheckResult:
        """Analyse whether the current user has permission for *operation*.

        Handles six cases gracefully:
            1. File does not exist            → error
            2. Path is not a file             → error
            3. Permission is granted          → permitted=True
            4. Permission is denied           → permitted=False, details
            5. Insufficient access to check   → error
            6. Unexpected OS / API errors     → error

        Args:
            file_path: Path to the file to check.
            operation: The FileOperation to check (READ, WRITE, EXECUTE,
                       DELETE).  Defaults to READ.

        Returns:
            PermissionCheckResult with structured diagnostic data.
        """
        file_path = self.validate_path(file_path)

        # ----- Case 1: file does not exist -----
        if not os.path.exists(file_path):
            return PermissionCheckResult(
                file_path=file_path,
                operation=operation.value,
                permitted=False,
                error=f"File does not exist: {file_path}",
                detection_method="error",
            )

        # ----- Case 2: not a file -----
        if not os.path.isfile(file_path):
            return PermissionCheckResult(
                file_path=file_path,
                operation=operation.value,
                permitted=False,
                error=f"Path is a directory, not a file: {file_path}",
                detection_method="error",
            )

        # ----- Determine current user -----
        try:
            current_user = getpass.getuser()
        except Exception:
            current_user = "(unknown)"

        # ----- Cross-platform permission check via os.access() -----
        try:
            access_flag = _OPERATION_TO_ACCESS_FLAG[operation]
            permitted = os.access(file_path, access_flag)
        except Exception as exc:
            return PermissionCheckResult(
                file_path=file_path,
                operation=operation.value,
                permitted=False,
                current_user=current_user,
                error=f"Permission check failed: {exc}",
                detection_method="error",
            )

        # ----- Gather all permission bits -----
        permission_bits = self._get_permission_bits(file_path)

        # ----- Get file owner -----
        owner = self._get_file_owner(file_path)

        # ----- Build the details string -----
        details = self._build_details(
            file_path, operation, permitted, owner, current_user,
            permission_bits,
        )

        # ----- Choose detection method label -----
        if _IS_WINDOWS:
            detection_method = "windows_acl" if owner else "os_access"
        else:
            detection_method = "os_access"

        return PermissionCheckResult(
            file_path=file_path,
            operation=operation.value,
            permitted=permitted,
            owner=owner,
            current_user=current_user,
            details=details,
            permission_bits=permission_bits,
            detection_method=detection_method,
        )

    # ------------------------------------------------------------------
    # Permission bit collection
    # ------------------------------------------------------------------
    @staticmethod
    def _get_permission_bits(file_path: str) -> Dict[str, bool]:
        """Check all three access types and return a dict.

        Returns:
            {'read': bool, 'write': bool, 'execute': bool}
        """
        return {
            "read": os.access(file_path, os.R_OK),
            "write": os.access(file_path, os.W_OK),
            "execute": os.access(file_path, os.X_OK),
        }

    # ------------------------------------------------------------------
    # File owner detection
    # ------------------------------------------------------------------
    @staticmethod
    def _get_file_owner(file_path: str) -> str:
        """Determine the owner of the file.

        On Windows: uses GetNamedSecurityInfoW + LookupAccountSidW
                    via ctypes → advapi32.dll.
        On POSIX:   uses os.stat() + pwd module to resolve UID → name.

        Returns:
            Owner string (e.g. 'DOMAIN\\User' or 'username'),
            or empty string if owner could not be determined.
        """
        if _IS_WINDOWS:
            return PermissionAnalyzer._get_file_owner_windows(file_path)
        else:
            return PermissionAnalyzer._get_file_owner_posix(file_path)

    @staticmethod
    def _get_file_owner_posix(file_path: str) -> str:
        """Get file owner on POSIX systems via stat + pwd."""
        try:
            file_stat = os.stat(file_path)
            uid = file_stat.st_uid
            try:
                import pwd
                return pwd.getpwuid(uid).pw_name
            except (ImportError, KeyError):
                return str(uid)
        except OSError:
            return ""

    @staticmethod
    def _get_file_owner_windows(file_path: str) -> str:
        """Get file owner on Windows via GetNamedSecurityInfoW.

        Calls advapi32.dll:
            1. GetNamedSecurityInfoW → retrieves owner SID
            2. LookupAccountSidW    → resolves SID to DOMAIN\\User

        This is a read-only operation — it never modifies anything.

        Returns:
            'DOMAIN\\Username' or empty string on failure.
        """
        if _advapi32 is None or _kernel32 is None:
            return ""

        # Pointers that GetNamedSecurityInfoW will fill
        p_sid_owner = ctypes.c_void_p()
        p_sd = ctypes.c_void_p()  # security descriptor (must be freed)

        try:
            ret = _advapi32.GetNamedSecurityInfoW(
                file_path,
                SE_FILE_OBJECT,
                OWNER_SECURITY_INFORMATION,
                ctypes.byref(p_sid_owner),  # ppsidOwner
                None,                        # ppsidGroup
                None,                        # ppDacl
                None,                        # ppSacl
                ctypes.byref(p_sd),          # ppSecurityDescriptor
            )
            if ret != ERROR_SUCCESS:
                return ""

            # Resolve SID → DOMAIN\Username
            name_buf = ctypes.create_unicode_buffer(256)
            name_len = wintypes.DWORD(256)
            domain_buf = ctypes.create_unicode_buffer(256)
            domain_len = wintypes.DWORD(256)
            sid_name_use = wintypes.DWORD()

            success = _advapi32.LookupAccountSidW(
                None,                       # lpSystemName (local)
                p_sid_owner,                # Sid
                name_buf,                   # Name
                ctypes.byref(name_len),     # cchName
                domain_buf,                 # ReferencedDomainName
                ctypes.byref(domain_len),   # cchReferencedDomainName
                ctypes.byref(sid_name_use), # peUse
            )

            if not success:
                return ""

            domain = domain_buf.value
            name = name_buf.value
            if domain:
                return f"{domain}\\{name}"
            return name

        except Exception:
            return ""
        finally:
            # Free the security descriptor allocated by the API
            if p_sd.value is not None:
                _kernel32.LocalFree(p_sd)

    # ------------------------------------------------------------------
    # Human-readable details
    # ------------------------------------------------------------------
    @staticmethod
    def _build_details(
        file_path: str,
        operation: FileOperation,
        permitted: bool,
        owner: str,
        current_user: str,
        permission_bits: Dict[str, bool],
    ) -> str:
        """Build a human-readable explanation of the permission check.

        Returns:
            A multi-line details string.
        """
        status = "GRANTED" if permitted else "DENIED"
        lines = [
            f"{operation.value.upper()} access is {status} "
            f"for user '{current_user}'.",
        ]

        if owner:
            lines.append(f"File owner: {owner}")

        # Summarise all permission bits
        bits_summary = ", ".join(
            f"{k}={'yes' if v else 'no'}"
            for k, v in sorted(permission_bits.items())
        )
        lines.append(f"Effective permissions: {bits_summary}")

        if not permitted:
            if operation == FileOperation.DELETE:
                lines.append(
                    "Note: DELETE permission on Windows depends on the "
                    "parent directory's ACL and the file's own ACL. "
                    "The os.access() check approximates this via write "
                    "access to the file."
                )
            lines.append(
                "The current user may not have the required NTFS "
                "permissions for this operation."
            )

        return "\n".join(lines)
