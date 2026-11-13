import numpy as np
from numpy.typing import NDArray

from mp3_quality_scanner.analysis.analyzers.click import ClickProcessor
from mp3_quality_scanner.domain.models import AnalysisResult

SAMPLE_RATE = 44100


def analyze_chunks(
    chunks: list[NDArray[np.float32]],
) -> AnalysisResult:
    processor = ClickProcessor()

    for chunk in chunks:
        processor.process(chunk)

    return processor.finish()


def click_positions(
    chunks: list[NDArray[np.float32]],
) -> list[float]:
    result = analyze_chunks(chunks)

    return [
        finding.position_seconds
        for finding in result.findings
        if finding.code == "POSSIBLE_CLICK" and finding.position_seconds is not None
    ]


def test_silence_has_no_clicks() -> None:
    samples = np.zeros(
        (SAMPLE_RATE, 2),
        dtype=np.float32,
    )

    assert click_positions([samples]) == []


def test_sine_wave_has_no_clicks() -> None:
    time = np.arange(SAMPLE_RATE) / SAMPLE_RATE

    sine = (0.5 * np.sin(2 * np.pi * 440 * time)).astype(np.float32)

    samples = np.column_stack((sine, sine))

    assert click_positions([samples]) == []


def test_isolated_click_detected() -> None:
    samples = np.zeros(
        (SAMPLE_RATE, 2),
        dtype=np.float32,
    )

    samples[SAMPLE_RATE // 2, 0] = 0.9

    positions = click_positions([samples])

    assert len(positions) == 1
    assert abs(positions[0] - 0.5) < 0.001


def test_click_at_chunk_end() -> None:
    samples = np.zeros(
        (4096, 2),
        dtype=np.float32,
    )

    samples[1023, 0] = 0.9

    positions = click_positions(
        [
            samples[:1024],
            samples[1024:2048],
            samples[2048:],
        ]
    )

    assert len(positions) == 1
    assert abs(positions[0] - 1023 / SAMPLE_RATE) < 0.001


def test_click_at_chunk_start() -> None:
    samples = np.zeros(
        (4096, 2),
        dtype=np.float32,
    )

    samples[1024, 0] = 0.9

    positions = click_positions(
        [
            samples[:1024],
            samples[1024:2048],
            samples[2048:],
        ]
    )

    assert len(positions) == 1
    assert abs(positions[0] - 1024 / SAMPLE_RATE) < 0.001


def test_no_duplicate_clicks() -> None:
    samples = np.zeros(
        (4096, 2),
        dtype=np.float32,
    )

    samples[1024, 0] = 0.9

    positions = click_positions(
        [
            samples[:1024],
            samples[1024:2048],
            samples[2048:3072],
            samples[3072:],
        ]
    )

    assert len(positions) == 1


def test_two_separated_clicks() -> None:
    samples = np.zeros(
        (8192, 2),
        dtype=np.float32,
    )

    samples[1024, 0] = 0.9
    samples[4096, 0] = 0.9

    positions = click_positions(
        [
            samples[:2048],
            samples[2048:4096],
            samples[4096:6144],
            samples[6144:],
        ]
    )

    assert len(positions) == 2


def test_chunking_does_not_change_results() -> None:
    samples = np.zeros(
        (8192, 2),
        dtype=np.float32,
    )

    samples[1024, 0] = 0.9
    samples[4096, 1] = -0.8

    whole = click_positions([samples])

    split = click_positions(
        [
            samples[:1000],
            samples[1000:1024],
            samples[1024:3000],
            samples[3000:4096],
            samples[4096:],
        ]
    )

    assert whole == split


def test_short_audio_does_not_fail() -> None:
    samples = np.zeros(
        (20, 2),
        dtype=np.float32,
    )

    result = analyze_chunks([samples])

    assert result.analyzer == "click"
    assert result.findings == []


def test_invalid_pcm_raises_error() -> None:
    samples = np.zeros(
        (1024, 2),
        dtype=np.float32,
    )

    samples[100, 0] = np.nan

    processor = ClickProcessor()

    try:
        processor.process(samples)
    except ValueError as exc:
        assert "Non-finite" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
