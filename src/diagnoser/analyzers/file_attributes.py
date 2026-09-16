"""
File Attribute Analyzer (stub).

Future milestone: will inspect file-system attributes such as
read-only, hidden, system, archive flags, and NTFS metadata
to identify potential causes of file-operation failures.
"""

from diagnoser.analyzers.base import BaseAnalyzer
from diagnoser.models import AnalyzerResult


class FileAttributeAnalyzer(BaseAnalyzer):
    """Analyses file-system attributes and metadata.

    Not yet implemented — placeholder for a future milestone.
    """

    def analyze(self, file_path: str) -> AnalyzerResult:
        """Analyse file attributes for the given file.

        Args:
            file_path: Absolute path to the file.

        Returns:
            AnalyzerResult with attribute-related findings.

        Raises:
            NotImplementedError: Always — not yet implemented.
        """
        raise NotImplementedError(
            "FileAttributeAnalyzer is not yet implemented (future milestone)."
        )
