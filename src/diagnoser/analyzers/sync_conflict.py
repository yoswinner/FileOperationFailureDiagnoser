"""
Synchronisation Conflict Detector (stub).

Future milestone: will detect synchronisation-related issues such
as cloud-sync locks (OneDrive, Dropbox), antivirus scanning holds,
and backup-software conflicts.
"""

from diagnoser.analyzers.base import BaseAnalyzer
from diagnoser.models import AnalyzerResult


class SyncConflictAnalyzer(BaseAnalyzer):
    """Detects synchronisation-related file conflicts.

    Not yet implemented — placeholder for a future milestone.
    """

    def analyze(self, file_path: str) -> AnalyzerResult:
        """Check for sync-related conflicts on the given file.

        Args:
            file_path: Absolute path to the file.

        Returns:
            AnalyzerResult with sync-conflict findings.

        Raises:
            NotImplementedError: Always — not yet implemented.
        """
        raise NotImplementedError(
            "SyncConflictAnalyzer is not yet implemented (future milestone)."
        )
