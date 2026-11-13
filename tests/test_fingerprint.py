from pathlib import Path

from mp3_quality_scanner.analysis.analyzers.base import Analyzer
from mp3_quality_scanner.domain.models import AnalysisResult
from mp3_quality_scanner.scanning.fingerprint import analyzer_fingerprint


class DummyAnalyzer(Analyzer):
    @property
    def name(self) -> str:
        return "dummy"

    @property
    def version(self) -> str:
        return "1"

    def analyze(self, path: Path) -> AnalysisResult:
        return AnalysisResult(analyzer=self.name)


class UpdatedDummyAnalyzer(DummyAnalyzer):
    @property
    def version(self) -> str:
        return "2"


def test_fingerprint_is_stable() -> None:
    first = analyzer_fingerprint([DummyAnalyzer()])
    second = analyzer_fingerprint([DummyAnalyzer()])

    assert first == second


def test_fingerprint_changes_with_version() -> None:
    first = analyzer_fingerprint([DummyAnalyzer()])
    second = analyzer_fingerprint([UpdatedDummyAnalyzer()])

    assert first != second
