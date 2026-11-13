from pathlib import Path
from unittest.mock import patch

import numpy as np

from mp3_quality_scanner.analysis.analyzers.click import ClickAnalyzer
from mp3_quality_scanner.analysis.analyzers.clipping import ClippingAnalyzer
from mp3_quality_scanner.analysis.pipeline import AudioPipeline


def test_pipeline_decodes_audio_once() -> None:
    samples = np.zeros(
        (44100, 2),
        dtype=np.float32,
    )

    samples[22050, 0] = 0.9

    pipeline = AudioPipeline(
        [
            ClippingAnalyzer(),
            ClickAnalyzer(),
        ]
    )

    with patch(
        "mp3_quality_scanner.analysis.pipeline.decode_audio",
        return_value=iter(
            [
                samples[:16384],
                samples[16384:32768],
                samples[32768:],
            ]
        ),
    ) as decoder:
        results = pipeline.analyze(Path("test.mp3"))

    decoder.assert_called_once()

    assert len(results) == 2

    by_analyzer = {result.analyzer: result for result in results}

    assert set(by_analyzer) == {
        "clipping",
        "click",
    }

    click_codes = {finding.code for finding in by_analyzer["click"].findings}

    assert "POSSIBLE_CLICK" in click_codes

    for result in results:
        assert not any(finding.code == "ANALYZER_FAILED" for finding in result.findings)


def test_pipeline_handles_decoder_failure() -> None:
    pipeline = AudioPipeline(
        [
            ClippingAnalyzer(),
            ClickAnalyzer(),
        ]
    )

    with patch(
        "mp3_quality_scanner.analysis.pipeline.decode_audio",
        side_effect=RuntimeError("Decoder failed"),
    ):
        results = pipeline.analyze(Path("broken.mp3"))

    assert len(results) == 2

    for result in results:
        assert any(finding.code == "ANALYZER_FAILED" for finding in result.findings)
