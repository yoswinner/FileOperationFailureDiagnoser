"""
Abstract base class for all analyzer modules.

Each analyzer examines one aspect of why a file operation might fail
(locks, permissions, attributes, sync conflicts) and returns a
structured result that the diagnosis engine can consume.
"""

import os
from abc import ABC, abstractmethod


class BaseAnalyzer(ABC):
    """Abstract base for all file-operation-failure analyzers.

    Subclasses must implement the analyze() method. This base class
    provides common helper methods for input validation.
    """

    @abstractmethod
    def analyze(self, file_path: str):
        """Analyse the given file path and return a structured result.

        Args:
            file_path: Absolute path to the file to analyse.

        Returns:
            A dataclass result specific to the analyzer type.
        """
        raise NotImplementedError

    @staticmethod
    def validate_path(file_path: str) -> str:
        """Normalise and return the absolute path.

        Args:
            file_path: A file path string.

        Returns:
            The normalised absolute path.
        """
        return os.path.abspath(os.path.normpath(file_path))

    @staticmethod
    def file_exists(file_path: str) -> bool:
        """Check whether the file exists.

        Args:
            file_path: An absolute file path.

        Returns:
            True if the path points to an existing file.
        """
        return os.path.isfile(file_path)
