from pathlib import Path

import pytest

from mp3_quality_scanner.domain.models import (
    AnalysisResult,
    AudioMetadata,
    Finding,
    ScanResult,
    Severity,
)
from mp3_quality_scanner.domain.quality import assess_quality


def make_result(
    *codes: str,
    duration_seconds: float = 300.0,
) -> ScanResult:
    return ScanResult(
        path=Path("test.mp3"),
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
                analyzer="click",
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


def test_clean_file_scores_100() -> None:
    assessment = assess_quality(make_result())

    assert assessment.score == 100
    assert assessment.label == "good"


def test_single_click_penalty() -> None:
    assessment = assess_quality(make_result("POSSIBLE_CLICK"))

    assert assessment.score == 97
    assert assessment.click_count == 1


def test_multiple_clicks() -> None:
    assessment = assess_quality(
        make_result(
            "POSSIBLE_CLICK",
            "POSSIBLE_CLICK",
            "POSSIBLE_CLICK",
        )
    )

    assert assessment.score == 91
    assert assessment.label == "good"


def test_clipping_penalties() -> None:
    assessment = assess_quality(
        make_result(
            "HIGH_CLIPPING_RATIO",
            "SUSTAINED_CLIPPING",
        )
    )

    assert assessment.score == 65


def test_click_penalty_is_capped() -> None:
    assessment = assess_quality(make_result(*(["POSSIBLE_CLICK"] * 100)))

    assert assessment.score == 40


@pytest.mark.parametrize(
    "code",
    [
        "EMPTY_AUDIO",
        "INVALID_PCM",
        "DECODE_FAILED",
        "PROBE_FAILED",
        "ANALYZER_FAILED",
    ],
)
def test_invalid_analysis_has_no_score(
    code: str,
) -> None:
    assessment = assess_quality(make_result(code))

    assert assessment.score is None
    assert assessment.label == "unknown"


def test_scan_result_quality_property() -> None:
    result = make_result("POSSIBLE_CLICK")

    assert result.quality_score == 97


@pytest.mark.parametrize(
    ("duration", "clicks", "expected_score"),
    [
        (60.0, 1, 85),
        (120.0, 2, 85),
        (300.0, 10, 70),
        (600.0, 10, 85),
        (120.0, 10, 40),
    ],
)
def test_click_rate_scoring(
    duration: float,
    clicks: int,
    expected_score: int,
) -> None:
    result = make_result(
        *(["POSSIBLE_CLICK"] * clicks),
        duration_seconds=duration,
    )

    assessment = assess_quality(result)

    assert assessment.score == expected_score
    assert assessment.click_count == clicks
    assert assessment.click_rate == pytest.approx(clicks * 60 / duration)


def test_missing_duration_with_clicks() -> None:
    result = make_result(
        "POSSIBLE_CLICK",
        duration_seconds=0.0,
    )

    assessment = assess_quality(result)

    assert assessment.score is None
    assert assessment.label == "unknown"
