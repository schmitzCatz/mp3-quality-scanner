import json
import subprocess
from pathlib import Path
from typing import Any

from mp3_quality_scanner.analysis.analyzers.base import Analyzer
from mp3_quality_scanner.domain.models import (
    AnalysisResult,
    AudioMetadata,
    Finding,
    Severity,
)


class IntegrityAnalyzer(Analyzer):
    @property
    def name(self) -> str:
        return "integrity"

    def analyze(self, path: Path) -> AnalysisResult:
        result = AnalysisResult(analyzer=self.name)

        try:
            result.metadata = self._probe(path)
        except (OSError, ValueError, RuntimeError) as exc:
            result.findings.append(
                Finding(
                    code="PROBE_FAILED",
                    severity=Severity.ERROR,
                    message=str(exc),
                )
            )

        try:
            self._decode(path)
        except (OSError, RuntimeError) as exc:
            result.findings.append(
                Finding(
                    code="DECODE_FAILED",
                    severity=Severity.ERROR,
                    message=str(exc),
                )
            )

        return result

    def _probe(self, path: Path) -> AudioMetadata:
        command = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "format=duration,bit_rate:stream=codec_name,sample_rate,channels",
            "-of",
            "json",
            str(path),
        ]

        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )

        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip())

        data: dict[str, Any] = json.loads(completed.stdout)
        streams = data.get("streams", [])

        if not streams:
            raise ValueError("No audio stream found")

        stream = streams[0]
        format_info = data.get("format", {})

        duration = format_info.get("duration")
        bitrate = format_info.get("bit_rate")

        return AudioMetadata(
            codec=str(stream.get("codec_name", "unknown")),
            duration_seconds=float(duration) if duration else None,
            bitrate=int(bitrate) if bitrate else None,
            sample_rate=(int(stream["sample_rate"]) if stream.get("sample_rate") else None),
            channels=(int(stream["channels"]) if stream.get("channels") else None),
        )

    def _decode(self, path: Path) -> None:
        command = [
            "ffmpeg",
            "-hide_banner",
            "-nostdin",
            "-v",
            "warning",
            "-xerror",
            "-i",
            str(path),
            "-map",
            "0:a:0",
            "-f",
            "null",
            "-",
        ]

        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=1800,
            check=False,
        )

        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or "Audio decoding failed")
