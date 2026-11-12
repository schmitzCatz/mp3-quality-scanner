import numpy as np
from numpy.typing import NDArray

from mp3_quality_scanner.analyzers.clipping import (
    ClippingProcessor,
)
from mp3_quality_scanner.models import AnalysisResult


def analyze_chunks(
    chunks: list[NDArray[np.float32]],
) -> AnalysisResult:
    processor = ClippingProcessor()

    for chunk in chunks:
        processor.process(chunk)

    return processor.finish()


def finding_codes(
    chunks: list[NDArray[np.float32]],
) -> set[str]:
    result = analyze_chunks(chunks)

    return {finding.code for finding in result.findings}


def test_silence_has_no_clipping() -> None:
    samples = np.zeros(
        (44100, 2),
        dtype=np.float32,
    )

    assert finding_codes([samples]) == set()


def test_empty_audio() -> None:
    result = analyze_chunks([])

    assert {finding.code for finding in result.findings} == {"EMPTY_AUDIO"}


def test_high_clipping_ratio() -> None:
    samples = np.zeros(
        (10000, 2),
        dtype=np.float32,
    )

    samples[100:200, 0] = 1.0

    codes = finding_codes([samples])

    assert "HIGH_CLIPPING_RATIO" in codes


def test_sustained_clipping() -> None:
    samples = np.zeros(
        (10000, 2),
        dtype=np.float32,
    )

    samples[100:120, 0] = 1.0

    codes = finding_codes([samples])

    assert "SUSTAINED_CLIPPING" in codes


def test_clipping_across_chunk_boundary() -> None:
    samples = np.zeros(
        (1000, 2),
        dtype=np.float32,
    )

    samples[496:504, 0] = 1.0

    codes = finding_codes(
        [
            samples[:500],
            samples[500:],
        ]
    )

    assert "SUSTAINED_CLIPPING" in codes


def test_no_false_clipping_below_threshold() -> None:
    samples = np.full(
        (10000, 2),
        0.8,
        dtype=np.float32,
    )

    assert finding_codes([samples]) == set()


def test_invalid_pcm_raises_error() -> None:
    samples = np.zeros(
        (1000, 2),
        dtype=np.float32,
    )

    samples[100, 0] = np.nan

    processor = ClippingProcessor()

    try:
        processor.process(samples)
    except ValueError as exc:
        assert "Non-finite" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
