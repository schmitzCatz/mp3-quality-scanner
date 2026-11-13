from dataclasses import dataclass

from mp3_quality_scanner.domain.models import ScanResult


@dataclass(frozen=True)
class QualityAssessment:
    score: int | None
    label: str
    click_count: int
    click_rate: float | None
    penalty: int


INVALID_CODES = frozenset(
    {
        "EMPTY_AUDIO",
        "INVALID_PCM",
        "DECODE_FAILED",
        "PROBE_FAILED",
        "ANALYZER_FAILED",
    }
)

PENALTIES = {
    "HIGH_CLIPPING_RATIO": 15,
    "SUSTAINED_CLIPPING": 20,
    "CLICK_FINDINGS_TRUNCATED": 10,
    "DROPOUT_FINDINGS_TRUNCATED": 10,
}

QUALITY_MODEL_VERSION = 3


def assess_quality(result: ScanResult) -> QualityAssessment:
    findings = result.findings
    codes = {finding.code for finding in findings}

    click_count = sum(finding.code == "POSSIBLE_CLICK" for finding in findings)

    duration = next(
        (
            analysis.metadata.duration_seconds
            for analysis in result.analyses
            if analysis.metadata is not None
            and analysis.metadata.duration_seconds is not None
            and analysis.metadata.duration_seconds > 0
        ),
        None,
    )

    click_rate = click_count * 60.0 / duration if duration is not None else None

    if codes & INVALID_CODES:
        return QualityAssessment(
            score=None,
            label="unknown",
            click_count=click_count,
            click_rate=click_rate,
            penalty=0,
        )

    # Without duration, a detected click cannot be
    # normalized reliably.
    if click_count > 0 and click_rate is None:
        return QualityAssessment(
            score=None,
            label="unknown",
            click_count=click_count,
            click_rate=None,
            penalty=0,
        )

    click_penalty = (
        min(
            60,
            round(15 * click_rate),
        )
        if click_rate is not None
        else 0
    )

    other_penalty = sum(value for code, value in PENALTIES.items() if code in codes)
    dropout_count = sum(finding.code == "POSSIBLE_DROPOUT" for finding in findings)

    dropout_penalty = min(dropout_count * 12, 60)

    penalty = min(100, click_penalty + dropout_penalty + other_penalty)
    score = 100 - penalty

    if score < 50:
        label = "critical"
    elif score < 80:
        label = "review"
    else:
        label = "good"

    return QualityAssessment(
        score=score,
        label=label,
        click_count=click_count,
        click_rate=click_rate,
        penalty=penalty,
    )
