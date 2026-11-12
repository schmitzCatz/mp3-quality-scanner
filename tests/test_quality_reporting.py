from pathlib import Path

from mp3_quality_scanner.models import (
    AnalysisResult,
    AudioMetadata,
    Finding,
    ScanResult,
    Severity,
)
from mp3_quality_scanner.repository import ScanRepository


def make_result(
    path: str,
    *codes: str,
    duration_seconds: float = 60.0,
) -> ScanResult:
    return ScanResult(
        path=Path(path),
        analyses=[
            AnalysisResult(
                analyzer="integrity",
                metadata=AudioMetadata(
                    codec="mp3",
                    duration_seconds=duration_seconds,
                    bitrate=320000,
                    sample_rate=44100,
                    channels=2,
                ),
            ),
            AnalysisResult(
                analyzer="test",
                findings=[
                    Finding(
                        code=code,
                        severity=Severity.WARNING,
                        message=code,
                    )
                    for code in codes
                ],
            ),
        ],
    )


def test_quality_summary(tmp_path: Path) -> None:
    with ScanRepository(tmp_path / "test.db") as repository:
        repository.save(
            "good.mp3",
            100,
            1,
            make_result("good.mp3"),
            "test-fingerprint",
        )

        repository.save(
            "review.mp3",
            100,
            1,
            make_result(
                "review.mp3",
                *(["POSSIBLE_CLICK"] * 3),
            ),
            "test-fingerprint",
        )

        repository.save(
            "critical.mp3",
            100,
            1,
            make_result(
                "critical.mp3",
                *(["POSSIBLE_CLICK"] * 10),
            ),
            "test-fingerprint",
        )

        summary = repository.get_quality_summary()

        assert summary.total == 3
        assert summary.good == 1
        assert summary.review == 1
        assert summary.critical == 1
        assert summary.unknown == 0


def test_worst_files_sorted_by_score(
    tmp_path: Path,
) -> None:
    with ScanRepository(tmp_path / "test.db") as repository:
        repository.save(
            "good.mp3",
            100,
            1,
            make_result("good.mp3"),
            "test-fingerprint",
        )

        repository.save(
            "critical.mp3",
            100,
            1,
            make_result(
                "critical.mp3",
                *(["POSSIBLE_CLICK"] * 10),
            ),
            "test-fingerprint",
        )

        files = repository.get_worst_files()

        assert [file.path for file in files] == [
            "critical.mp3",
            "good.mp3",
        ]

        assert files[0].score == 40
        assert files[1].score == 100
