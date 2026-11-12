from pathlib import Path

from mp3_quality_scanner.models import (
    AnalysisResult,
    Finding,
    ScanResult,
    Severity,
)
from mp3_quality_scanner.repository import ScanRepository


def test_save_and_skip_unchanged_file(tmp_path: Path) -> None:
    database = tmp_path / "scan.db"
    path = tmp_path / "track.mp3"

    result = ScanResult(
        path=path,
        analyses=[AnalysisResult(analyzer="integrity")],
    )

    with ScanRepository(database) as repository:
        assert not repository.is_current("track.mp3", 100, 123)

        repository.save(
            relative_path="track.mp3",
            size=100,
            mtime_ns=123,
            result=result,
        )

        assert repository.is_current("track.mp3", 100, 123)
        assert not repository.is_current("track.mp3", 200, 123)
        assert not repository.is_current("track.mp3", 100, 456)


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
        repository.save("track.mp3", 100, 123, broken)
        repository.save("track.mp3", 100, 123, repaired)

        output = tmp_path / "report.csv"
        repository.export_csv(output)

    content = output.read_text(encoding="utf-8")

    assert "DECODE_FAILED" not in content
    assert "track.mp3" in content
    assert "ok" in content
