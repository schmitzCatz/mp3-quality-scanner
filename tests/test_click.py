from pathlib import Path
from unittest.mock import patch

import numpy as np

from mp3_quality_scanner.analyzers.click import ClickAnalyzer


def analyze_samples(
    samples: np.ndarray,
) -> list[str]:
    with patch(
        "mp3_quality_scanner.analyzers.click.decode_audio",
        return_value=iter([samples]),
    ):
        result = ClickAnalyzer().analyze(Path("test.mp3"))

    return [finding.code for finding in result.findings]


def test_silence_has_no_clicks() -> None:
    samples = np.zeros(
        (44100, 2),
        dtype=np.float32,
    )

    assert analyze_samples(samples) == []


def test_sine_wave_has_no_clicks() -> None:
    sample_rate = 22050
    time = np.arange(sample_rate) / sample_rate

    sine = (0.5 * np.sin(2 * np.pi * 440 * time)).astype(np.float32)

    samples = np.column_stack((sine, sine))

    assert analyze_samples(samples) == []


def test_isolated_impulse_detected() -> None:
    samples = np.zeros(
        (22050, 2),
        dtype=np.float32,
    )

    samples[11025, 0] = 0.9

    assert "POSSIBLE_CLICK" in analyze_samples(samples)


def test_click_position_is_reported() -> None:
    samples = np.zeros(
        (22050, 2),
        dtype=np.float32,
    )

    samples[11025, 0] = 0.9

    with patch(
        "mp3_quality_scanner.analyzers.click.decode_audio",
        return_value=iter([samples]),
    ):
        result = ClickAnalyzer().analyze(Path("test.mp3"))

    assert result.findings
    assert abs(result.findings[0].position_seconds - 0.5) < 0.01


def test_short_audio_does_not_fail() -> None:
    samples = np.zeros(
        (20, 2),
        dtype=np.float32,
    )

    assert analyze_samples(samples) == []
