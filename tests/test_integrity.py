import json
import subprocess
from pathlib import Path
from unittest.mock import patch

from mp3_quality_scanner.analyzers.integrity import IntegrityAnalyzer
from mp3_quality_scanner.models import Severity


def test_valid_mp3(tmp_path: Path) -> None:
    path = tmp_path / "test.mp3"
    path.touch()

    probe_result = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout=json.dumps(
            {
                "streams": [
                    {
                        "codec_name": "mp3",
                        "sample_rate": "44100",
                        "channels": 2,
                    }
                ],
                "format": {
                    "duration": "180.5",
                    "bit_rate": "320000",
                },
            }
        ),
        stderr="",
    )

    decode_result = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout="",
        stderr="",
    )

    with patch(
        "mp3_quality_scanner.analyzers.integrity.subprocess.run",
        side_effect=[probe_result, decode_result],
    ):
        result = IntegrityAnalyzer().analyze(path)

    assert result.findings == []
    assert result.metadata is not None
    assert result.metadata.codec == "mp3"
    assert result.metadata.duration_seconds == 180.5


def test_decode_failure(tmp_path: Path) -> None:
    path = tmp_path / "broken.mp3"
    path.touch()

    probe_result = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout='{"streams": [{"codec_name": "mp3"}]}',
        stderr="",
    )

    decode_result = subprocess.CompletedProcess(
        args=[],
        returncode=1,
        stdout="",
        stderr="Invalid audio frame",
    )

    with patch(
        "mp3_quality_scanner.analyzers.integrity.subprocess.run",
        side_effect=[probe_result, decode_result],
    ):
        result = IntegrityAnalyzer().analyze(path)

    assert len(result.findings) == 1
    assert result.findings[0].code == "DECODE_FAILED"
    assert result.findings[0].severity == Severity.ERROR
