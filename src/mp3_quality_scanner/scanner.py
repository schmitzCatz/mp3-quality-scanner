from concurrent.futures import (
    FIRST_COMPLETED,
    Future,
    ThreadPoolExecutor,
    wait,
)
from dataclasses import dataclass
from pathlib import Path

from mp3_quality_scanner.analyzers.base import Analyzer
from mp3_quality_scanner.discovery import discover_mp3_files
from mp3_quality_scanner.fingerprint import analyzer_fingerprint
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
        workers: int = 2,
    ) -> ScanStatistics:
        if workers < 1:
            raise ValueError("workers must be >= 1")

        stats = ScanStatistics()
        files = discover_mp3_files(directory)
        stats.discovered = len(files)

        fingerprint = analyzer_fingerprint(self.analyzers)

        pending: dict[Future[ScanResult], tuple[str, int, int]] = {}

        def collect_completed(
            futures: set[Future[ScanResult]],
        ) -> None:
            for future in futures:
                relative_path, size, mtime_ns = pending.pop(future)
                result = future.result()

                scan_state = (
                    "failed"
                    if any(finding.code == "ANALYZER_FAILED" for finding in result.findings)
                    else "completed"
                )

                repository.save(
                    relative_path=relative_path,
                    size=size,
                    mtime_ns=mtime_ns,
                    result=result,
                    fingerprint=fingerprint,
                    scan_state=scan_state,
                )

                stats.analyzed += 1

                if result.status == "error":
                    stats.errors += 1
                elif result.status == "warning":
                    stats.warnings += 1

                print(
                    f"[{stats.analyzed}/{stats.discovered}] "
                    f"{result.status.upper()}: {relative_path}",
                    flush=True,
                )

        with ThreadPoolExecutor(max_workers=workers) as executor:
            for path in files:
                relative_path = path.relative_to(directory).as_posix()

                try:
                    stat = path.stat()
                except OSError as exc:
                    print(f"STAT ERROR: {path}: {exc}")
                    stats.errors += 1
                    continue

                if not force and repository.is_current(
                    relative_path,
                    stat.st_size,
                    stat.st_mtime_ns,
                    fingerprint,
                ):
                    stats.skipped += 1
                    continue

                future = executor.submit(self.scan_file, path)
                pending[future] = (
                    relative_path,
                    stat.st_size,
                    stat.st_mtime_ns,
                )

                if len(pending) >= workers * 2:
                    completed, _ = wait(
                        pending,
                        return_when=FIRST_COMPLETED,
                    )
                    collect_completed(completed)

            while pending:
                completed, _ = wait(
                    pending,
                    return_when=FIRST_COMPLETED,
                )
                collect_completed(completed)

        return stats
