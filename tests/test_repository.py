from pathlib import Path

from mp3_quality_scanner.models import (
    AnalysisResult,
    Finding,
    ScanResult,
    Severity,
)
from mp3_quality_scanner.repository import ScanRepository

FINGERPRINT_V1 = "test-fingerprint-v1"
FINGERPRINT_V2 = "test-fingerprint-v2"


def test_save_and_skip_unchanged_file(tmp_path: Path) -> None:
    database = tmp_path / "scan.db"
    path = tmp_path / "track.mp3"

    result = ScanResult(
        path=path,
        analyses=[AnalysisResult(analyzer="integrity")],
    )

    with ScanRepository(database) as repository:
        assert not repository.is_current("track.mp3", 100, 123, FINGERPRINT_V1)

        repository.save(
            relative_path="track.mp3",
            size=100,
            mtime_ns=123,
            result=result,
            fingerprint=FINGERPRINT_V1,
        )

        assert repository.is_current("track.mp3", 100, 123, FINGERPRINT_V1)
        assert not repository.is_current("track.mp3", 200, 123, FINGERPRINT_V1)
        assert not repository.is_current("track.mp3", 100, 456, FINGERPRINT_V1)


def test_fingerprint_invalidates_cache(tmp_path: Path) -> None:
    database = tmp_path / "scan.db"
    path = tmp_path / "track.mp3"

    result = ScanResult(
        path=path,
        analyses=[AnalysisResult(analyzer="integrity")],
    )

    with ScanRepository(database) as repository:
        repository.save(
            relative_path="track.mp3",
            size=100,
            mtime_ns=123,
            result=result,
            fingerprint=FINGERPRINT_V1,
        )

        assert repository.is_current("track.mp3", 100, 123, FINGERPRINT_V1)

        assert not repository.is_current("track.mp3", 100, 123, FINGERPRINT_V2)


def test_failed_scan_is_not_cached(tmp_path: Path) -> None:
    database = tmp_path / "scan.db"
    path = tmp_path / "track.mp3"

    result = ScanResult(
        path=path,
        analyses=[
            AnalysisResult(
                analyzer="integrity",
                findings=[
                    Finding(
                        code="ANALYZER_FAILED",
                        severity=Severity.ERROR,
                        message="Unexpected analyzer error",
                    )
                ],
            )
        ],
    )

    with ScanRepository(database) as repository:
        repository.save(
            relative_path="track.mp3",
            size=100,
            mtime_ns=123,
            result=result,
            fingerprint=FINGERPRINT_V1,
            scan_state="failed",
        )

        assert not repository.is_current("track.mp3", 100, 123, FINGERPRINT_V1)


def test_findings_are_replaced_on_rescan(tmp_path: Path) -> None:
    database = tmp_path / "scan.db"
    path = tmp_path / "track.mp3"

    broken = ScanResult(
        path=path,
        analyses=[
            AnalysisResult(
                analyzer="integrity",
                findings=[
                    Finding(
                        code="DECODE_FAILED",
                        severity=Severity.ERROR,
                        message="Invalid frame",
                    )
                ],
            )
        ],
    )

    repaired = ScanResult(
        path=path,
        analyses=[AnalysisResult(analyzer="integrity")],
    )

    with ScanRepository(database) as repository:
        repository.save(
            relative_path="track.mp3",
            size=100,
            mtime_ns=123,
            result=broken,
            fingerprint=FINGERPRINT_V1,
        )

        repository.save(
            relative_path="track.mp3",
            size=100,
            mtime_ns=123,
            result=repaired,
            fingerprint=FINGERPRINT_V1,
        )

        output = tmp_path / "report.csv"
        repository.export_csv(output)

    content = output.read_text(encoding="utf-8")

    assert "DECODE_FAILED" not in content
    assert "track.mp3" in content
    assert "ok" in content
