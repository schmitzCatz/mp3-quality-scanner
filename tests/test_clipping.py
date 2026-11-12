from pathlib import Path
from unittest.mock import patch

import numpy as np

from mp3_quality_scanner.analyzers.clipping import ClippingAnalyzer


def test_normal_audio_has_no_findings() -> None:
    samples = np.array(
        [
            [0.1, -0.1],
            [0.5, -0.5],
            [0.8, -0.8],
        ],
        dtype=np.float32,
    )

    with patch(
        "mp3_quality_scanner.analyzers.clipping.decode_audio",
        return_value=iter([samples]),
    ):
        result = ClippingAnalyzer().analyze(Path("test.mp3"))

    assert result.findings == []


def test_clipping_ratio_detected() -> None:
    samples = np.ones((1000, 2), dtype=np.float32)

    with patch(
        "mp3_quality_scanner.analyzers.clipping.decode_audio",
        return_value=iter([samples]),
    ):
        result = ClippingAnalyzer().analyze(Path("test.mp3"))

    codes = {finding.code for finding in result.findings}

    assert "HIGH_CLIPPING_RATIO" in codes
    assert "SUSTAINED_CLIPPING" in codes


def test_sustained_clipping_across_chunks() -> None:
    first = np.array(
        [[0.0, 0.0]] + [[1.0, 0.0]] * 5,
        dtype=np.float32,
    )
    second = np.array(
        [[1.0, 0.0]] * 5 + [[0.0, 0.0]],
        dtype=np.float32,
    )

    with patch(
        "mp3_quality_scanner.analyzers.clipping.decode_audio",
        return_value=iter([first, second]),
    ):
        result = ClippingAnalyzer().analyze(Path("test.mp3"))

    codes = {finding.code for finding in result.findings}

    assert "SUSTAINED_CLIPPING" in codes


def test_empty_audio_detected() -> None:
    with patch(
        "mp3_quality_scanner.analyzers.clipping.decode_audio",
        return_value=iter([]),
    ):
        result = ClippingAnalyzer().analyze(Path("test.mp3"))

    assert result.findings[0].code == "EMPTY_AUDIO"
