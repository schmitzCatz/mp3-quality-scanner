from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from mp3_quality_scanner.analysis.analyzers.click import ClickAnalyzer
from mp3_quality_scanner.analysis.analyzers.clipping import ClippingAnalyzer


@pytest.mark.parametrize(
    "analyzer",
    [
        ClippingAnalyzer(),
        ClickAnalyzer(),
    ],
)
def test_standalone_analyzer_uses_decoder(
    analyzer: ClippingAnalyzer | ClickAnalyzer,
) -> None:
    samples = np.zeros(
        (44100, 2),
        dtype=np.float32,
    )

    with patch(
        "mp3_quality_scanner.analysis.analyzers.streaming.decode_audio",
        return_value=iter([samples]),
    ) as decoder:
        result = analyzer.analyze(Path("test.mp3"))

    decoder.assert_called_once_with(
        Path("test.mp3"),
        sample_rate=44100,
        channels=2,
    )

    assert result.analyzer == analyzer.name
