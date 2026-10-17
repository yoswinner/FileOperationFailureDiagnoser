"""
File Attribute Analyzer.

Inspects file-system attributes (read-only, hidden, system, archive,
reparse point, and offline) to identify attribute-related causes of
file-operation failures.

On Windows, attributes are extracted using Python's os.stat().st_file_attributes
with a native Win32 GetFileAttributesW fallback via ctypes.

On non-Windows platforms (macOS/Linux), a portable POSIX stat fallback
is used for development and cross-platform testing, clearly marking
unsupported Windows-specific attributes as None.

Safety:
    This analyzer is strictly read-only. It never modifies, adds, or
    removes file attributes.
"""

import os
import stat
import sys
from typing import List, Optional

from diagnoser.analyzers.base import BaseAnalyzer
from diagnoser.models import FileAttributeResult

# ---------------------------------------------------------------------------
# Platform check and Windows-specific imports
# ---------------------------------------------------------------------------
_IS_WINDOWS = sys.platform == "win32"

if _IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    try:
        _kernel32 = ctypes.windll.kernel32
    except OSError:
        _kernel32 = None
else:
    _kernel32 = None

# ---------------------------------------------------------------------------
# Windows File Attribute Constants (from winnt.h / stat module)
# ---------------------------------------------------------------------------
FILE_ATTRIBUTE_READONLY = 0x00000001
FILE_ATTRIBUTE_HIDDEN = 0x00000002
FILE_ATTRIBUTE_SYSTEM = 0x00000004
FILE_ATTRIBUTE_DIRECTORY = 0x00000010
FILE_ATTRIBUTE_ARCHIVE = 0x00000020
FILE_ATTRIBUTE_DEVICE = 0x00000040
FILE_ATTRIBUTE_NORMAL = 0x00000080
FILE_ATTRIBUTE_TEMPORARY = 0x00000100
FILE_ATTRIBUTE_SPARSE_FILE = 0x00000200
FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
FILE_ATTRIBUTE_COMPRESSED = 0x00000800
FILE_ATTRIBUTE_OFFLINE = 0x00001000
FILE_ATTRIBUTE_NOT_CONTENT_INDEXED = 0x00002000
FILE_ATTRIBUTE_ENCRYPTED = 0x00004000
INVALID_FILE_ATTRIBUTES = 0xFFFFFFFF

# Mapping of attribute bitmasks to human-readable names
_ATTRIBUTE_FLAG_NAMES = [
    (FILE_ATTRIBUTE_READONLY, "READONLY"),
    (FILE_ATTRIBUTE_HIDDEN, "HIDDEN"),
    (FILE_ATTRIBUTE_SYSTEM, "SYSTEM"),
    (FILE_ATTRIBUTE_ARCHIVE, "ARCHIVE"),
    (FILE_ATTRIBUTE_TEMPORARY, "TEMPORARY"),
    (FILE_ATTRIBUTE_SPARSE_FILE, "SPARSE_FILE"),
    (FILE_ATTRIBUTE_REPARSE_POINT, "REPARSE_POINT"),
    (FILE_ATTRIBUTE_COMPRESSED, "COMPRESSED"),
    (FILE_ATTRIBUTE_OFFLINE, "OFFLINE"),
    (FILE_ATTRIBUTE_ENCRYPTED, "ENCRYPTED"),
]


class FileAttributeAnalyzer(BaseAnalyzer):
    """Analyses file-system attributes and metadata.

    Evaluates whether attributes like read-only, hidden, system, or
    offline may prevent intended file operations.

    Usage:
        analyzer = FileAttributeAnalyzer()
        result = analyzer.analyze(r"C:\\path\\to\\file.txt")
        if result.is_readonly:
            print("File is marked read-only.")
    """

    def analyze(self, file_path: str) -> FileAttributeResult:
        """Analyse file-system attributes for the given file path.

        Handles five cases gracefully:
            1. File does not exist            → error, detection_method='error'
            2. Path is a directory            → error, detection_method='error'
            3. Windows attributes detected     → populated result, detection_method='windows_stat'
            4. Non-Windows POSIX inspection    → populated result, detection_method='posix_stat'
            5. Inaccessible / OS exception    → error with exception details

        Args:
            file_path: Absolute or relative path to the file.

        Returns:
            FileAttributeResult with structured attribute findings.
        """
        file_path = self.validate_path(file_path)

        # ----- Case 1: file does not exist -----
        if not os.path.exists(file_path):
            return FileAttributeResult(
                file_path=file_path,
                error=f"File does not exist: {file_path}",
                detection_method="error",
            )

        # ----- Case 2: path is a directory -----
        if not os.path.isfile(file_path):
            return FileAttributeResult(
                file_path=file_path,
                error=f"Path is a directory, not a file: {file_path}",
                detection_method="error",
            )

        # ----- Cases 3, 4, 5: Operating system attribute inspection -----
        try:
            if _IS_WINDOWS:
                return self._analyze_windows(file_path)
            else:
                return self._analyze_posix(file_path)
        except PermissionError as exc:
            return FileAttributeResult(
                file_path=file_path,
                error=f"Permission denied accessing file attributes: {exc}",
                detection_method="error",
            )
        except Exception as exc:
            return FileAttributeResult(
                file_path=file_path,
                error=f"Failed to read file attributes: {exc}",
                detection_method="error",
            )

    # ------------------------------------------------------------------
    # Windows implementation
    # ------------------------------------------------------------------

    @staticmethod
    def _analyze_windows(file_path: str) -> FileAttributeResult:
        """Extract Windows file attributes using os.stat with Win32 fallback."""
        raw_attrs: Optional[int] = None

        # 1. Primary inspection: os.stat().st_file_attributes
        try:
            st = os.stat(file_path)
            raw_attrs = getattr(st, "st_file_attributes", None)
        except PermissionError:
            raise
        except OSError:
            pass

        # 2. Secondary fallback: kernel32.GetFileAttributesW via ctypes
        if raw_attrs is None and _kernel32 is not None:
            try:
                ret = _kernel32.GetFileAttributesW(ctypes.c_wchar_p(file_path))
                if ret != INVALID_FILE_ATTRIBUTES:
                    raw_attrs = int(ret)
            except Exception:
                pass

        if raw_attrs is None:
            return FileAttributeResult(
                file_path=file_path,
                error="Could not retrieve Windows file attributes.",
                detection_method="error",
            )

        # Decode individual standard bit flags
        is_readonly = bool(raw_attrs & FILE_ATTRIBUTE_READONLY)
        is_hidden = bool(raw_attrs & FILE_ATTRIBUTE_HIDDEN)
        is_system = bool(raw_attrs & FILE_ATTRIBUTE_SYSTEM)
        is_archive = bool(raw_attrs & FILE_ATTRIBUTE_ARCHIVE)
        is_reparse_point = bool(raw_attrs & FILE_ATTRIBUTE_REPARSE_POINT)
        is_offline = bool(raw_attrs & FILE_ATTRIBUTE_OFFLINE)

        # Build list of active attribute names
        attributes_list: List[str] = [
            name
            for mask, name in _ATTRIBUTE_FLAG_NAMES
            if (raw_attrs & mask)
        ]

        return FileAttributeResult(
            file_path=file_path,
            is_readonly=is_readonly,
            is_hidden=is_hidden,
            is_system=is_system,
            is_archive=is_archive,
            is_reparse_point=is_reparse_point,
            is_offline=is_offline,
            raw_attributes=raw_attrs,
            attributes_list=attributes_list,
            detection_method="windows_stat",
        )

    # ------------------------------------------------------------------
    # Non-Windows POSIX fallback
    # ------------------------------------------------------------------

    @staticmethod
    def _analyze_posix(file_path: str) -> FileAttributeResult:
        """Portable fallback for macOS/Linux cross-platform development."""
        st = os.stat(file_path)

        # On POSIX, read-only is determined by absence of user write bit
        is_readonly = not bool(st.st_mode & stat.S_IWUSR)
        # On POSIX, hidden files start with a dot
        is_hidden = os.path.basename(file_path).startswith(".")
        is_reparse_point = os.path.islink(file_path)

        attributes_list: List[str] = []
        if is_readonly:
            attributes_list.append("READONLY")
        if is_hidden:
            attributes_list.append("HIDDEN")
        if is_reparse_point:
            attributes_list.append("REPARSE_POINT")

        return FileAttributeResult(
            file_path=file_path,
            is_readonly=is_readonly,
            is_hidden=is_hidden,
            is_system=None,       # Not applicable / cannot determine on POSIX
            is_archive=None,      # Not applicable / cannot determine on POSIX
            is_reparse_point=is_reparse_point,
            is_offline=None,      # Not applicable / cannot determine on POSIX
            raw_attributes=int(st.st_mode),
            attributes_list=attributes_list,
            detection_method="posix_stat",
        )
