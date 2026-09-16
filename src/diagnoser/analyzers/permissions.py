"""
Permission and Ownership Analyzer (stub).

Future milestone: will analyse NTFS permissions, ownership, and
ACLs to determine whether the current user has sufficient rights
to perform a file operation.
"""

from diagnoser.analyzers.base import BaseAnalyzer
from diagnoser.models import AnalyzerResult


class PermissionAnalyzer(BaseAnalyzer):
    """Analyses file permissions and ownership.

    Not yet implemented — placeholder for a future milestone.
    """

    def analyze(self, file_path: str) -> AnalyzerResult:
        """Analyse permissions for the given file.

        Args:
            file_path: Absolute path to the file.

        Returns:
            AnalyzerResult with permission-related findings.

        Raises:
            NotImplementedError: Always — not yet implemented.
        """
        raise NotImplementedError(
            "PermissionAnalyzer is not yet implemented (future milestone)."
        )
