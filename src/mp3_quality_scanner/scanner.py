
from collections.abc import Callable
from concurrent.futures import (
    FIRST_COMPLETED,
    Future,
    ThreadPoolExecutor,
    wait,
)
from dataclasses import dataclass
from enum import StrEnum
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


class ScanEventType(StrEnum):
    DISCOVERED = "discovered"
    STARTED = "started"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(frozen=True)
class ScanEvent:
    type: ScanEventType
    path: str | None = None
    total: int | None = None
    status: str | None = None


ScanCallback = Callable[[ScanEvent], None]


class ScanRunner:
    def __init__(self, analyzers: list[Analyzer]) -> None:
        self.analyzers = analyzers

    def scan_file(self, path: Path) -> ScanResult:
        """Execute all analyzers for a single audio file."""
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
        callback: ScanCallback | None = None,
    ) -> ScanStatistics:
        """Scan MP3 files concurrently and persist results."""

        if workers < 1:
            raise ValueError("workers must be >= 1")

        stats = ScanStatistics()

        def emit(event: ScanEvent) -> None:
            if callback is not None:
                callback(event)

        # Discover files
        files = discover_mp3_files(directory)
        stats.discovered = len(files)

        emit(
            ScanEvent(
                type=ScanEventType.DISCOVERED,
                total=stats.discovered,
            )
        )

        # Fingerprint identifies the current analyzer pipeline.
        fingerprint = analyzer_fingerprint(self.analyzers)

        # Futures are mapped to their file metadata.
        pending: dict[
            Future[ScanResult],
            tuple[str, int, int],
        ] = {}

        def collect_completed(
            futures: set[Future[ScanResult]],
        ) -> None:
            """Collect worker results and persist them in the main thread."""

            for future in futures:
                relative_path, size, mtime_ns = pending.pop(future)

                try:
                    result = future.result()

                    # Unexpected analyzer failures are retryable.
                    scan_state = (
                        "failed"
                        if any(
                            finding.code == "ANALYZER_FAILED"
                            for finding in result.findings
                        )
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

                except Exception:
                    stats.errors += 1

                    emit(
                        ScanEvent(
                            type=ScanEventType.FAILED,
                            path=relative_path,
                            status="error",
                        )
                    )

                    # Continue processing other files.
                    continue

                stats.analyzed += 1

                if result.status == "error":
                    stats.errors += 1

                elif result.status == "warning":
                    stats.warnings += 1

                emit(
                    ScanEvent(
                        type=ScanEventType.COMPLETED,
                        path=relative_path,
                        status=result.status,
                    )
                )

        # Run analyzers concurrently.
        with ThreadPoolExecutor(max_workers=workers) as executor:
            for path in files:
                relative_path = path.relative_to(
                    directory
                ).as_posix()

                try:
                    stat = path.stat()

                except OSError:
                    stats.errors += 1

                    emit(
                        ScanEvent(
                            type=ScanEventType.FAILED,
                            path=relative_path,
                            status="error",
                        )
                    )
                    continue

                # Skip files that have already been analyzed.
                if not force and repository.is_current(
                    relative_path,
                    stat.st_size,
                    stat.st_mtime_ns,
                    fingerprint,
                ):
                    stats.skipped += 1

                    emit(
                        ScanEvent(
                            type=ScanEventType.SKIPPED,
                            path=relative_path,
                        )
                    )
                    continue

                # Submit analysis task.
                future = executor.submit(
                    self.scan_file,
                    path,
                )

                pending[future] = (
                    relative_path,
                    stat.st_size,
                    stat.st_mtime_ns,
                )

                emit(
                    ScanEvent(
                        type=ScanEventType.STARTED,
                        path=relative_path,
                    )
                )

                # Limit queued work to avoid unbounded memory use.
                if len(pending) >= workers * 2:
                    completed, _ = wait(
                        pending,
                        return_when=FIRST_COMPLETED,
                    )

                    collect_completed(completed)

            # Process remaining tasks.
            while pending:
                completed, _ = wait(
                    pending,
                    return_when=FIRST_COMPLETED,
                )

                collect_completed(completed)

        return stats
