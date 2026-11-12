from pathlib import Path

from mp3_quality_scanner.analyzers.base import Analyzer
from mp3_quality_scanner.discovery import discover_mp3_files
from mp3_quality_scanner.models import (
    AnalysisResult,
    Finding,
    ScanResult,
    Severity,
)


class ScanRunner:
    def __init__(self, analyzers: list[Analyzer]) -> None:
        self.analyzers = analyzers

    def scan_file(self, path: Path) -> ScanResult:
        result = ScanResult(path=path)

        for analyzer in self.analyzers:
            try:
                analysis = analyzer.analyze(path)
            except Exception as exc:
                analysis = AnalysisResult(
                    analyzer=analyzer.name,
                    findings=[
                        Finding(
                            code="ANALYZER_FAILED",
                            severity=Severity.ERROR,
                            message=str(exc),
                        )
                    ],
                )

            result.analyses.append(analysis)

        return result

    def scan_directory(self, directory: Path) -> list[ScanResult]:
        files = discover_mp3_files(directory)

        return [self.scan_file(path) for path in files]
