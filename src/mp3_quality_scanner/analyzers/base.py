from abc import ABC, abstractmethod
from pathlib import Path

from mp3_quality_scanner.models import AnalysisResult


class Analyzer(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique analyzer identifier."""

    @property
    def version(self) -> str:
        """Algorithm version used for cache invalidation."""
        return "1"

    @abstractmethod
    def analyze(self, path: Path) -> AnalysisResult:
        """Analyze an audio file and return findings."""
