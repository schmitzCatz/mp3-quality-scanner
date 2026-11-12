from dataclasses import dataclass
from pathlib import Path

from mp3_quality_scanner.analyzers.base import Analyzer
from mp3_quality_scanner.discovery import discover_mp3_files
from mp3_quality_scanner.models import (
    AnalysisResult,
    Finding,
    ScanResult,
    Severity,
)
from mp3_quality_scanner.repository import ScanRepository


@dataclass
class ScanStatistics:
    discovered: int = 0
    analyzed: int = 0
    skipped: int = 0
    errors: int = 0
    warnings: int = 0


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

    def scan_directory(
        self,
        directory: Path,
        repository: ScanRepository,
        force: bool = False,
    ) -> ScanStatistics:
        stats = ScanStatistics()

        files = discover_mp3_files(directory)
        stats.discovered = len(files)

        for index, path in enumerate(files, start=1):
            relative_path = path.relative_to(directory).as_posix()

            try:
                stat = path.stat()
            except OSError as exc:
                print(f"[{index}/{len(files)}] STAT ERROR: {path}: {exc}")
                stats.errors += 1
                continue

            if not force and repository.is_current(
                relative_path,
                stat.st_size,
                stat.st_mtime_ns,
            ):
                stats.skipped += 1
                continue

            result = self.scan_file(path)

            repository.save(
                relative_path=relative_path,
                size=stat.st_size,
                mtime_ns=stat.st_mtime_ns,
                result=result,
            )

            stats.analyzed += 1

            if result.status == "error":
                stats.errors += 1
            elif result.status == "warning":
                stats.warnings += 1

            print(
                f"[{index}/{len(files)}] {result.status.upper()}: {relative_path}",
                flush=True,
            )

        return stats
