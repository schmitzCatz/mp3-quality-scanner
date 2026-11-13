from collections.abc import Sequence
from pathlib import Path

from mp3_quality_scanner.analysis.analyzers.streaming import AudioProcessor, StreamingAnalyzer
from mp3_quality_scanner.analysis.audio import decode_audio
from mp3_quality_scanner.domain.models import (
    AnalysisResult,
    Finding,
    Severity,
)


class AudioPipeline:
    SAMPLE_RATE = 44100
    CHANNELS = 2

    def __init__(
        self,
        analyzers: Sequence[StreamingAnalyzer],
    ) -> None:
        self.analyzers = analyzers

    def analyze(self, path: Path) -> list[AnalysisResult]:
        processors: list[AudioProcessor] = [
            analyzer.create_processor() for analyzer in self.analyzers
        ]

        failed: dict[int, str] = {}

        try:
            for chunk in decode_audio(
                path,
                sample_rate=self.SAMPLE_RATE,
                channels=self.CHANNELS,
            ):
                for index, processor in enumerate(processors):
                    if index in failed:
                        continue

                    try:
                        processor.process(chunk)
                    except Exception as exc:
                        failed[index] = str(exc)

        except Exception as exc:
            for index in range(len(processors)):
                failed.setdefault(
                    index,
                    f"PCM decoding failed: {exc}",
                )

        results: list[AnalysisResult] = []

        for index, (analyzer, processor) in enumerate(zip(self.analyzers, processors, strict=True)):
            if index in failed:
                results.append(
                    AnalysisResult(
                        analyzer=analyzer.name,
                        findings=[
                            Finding(
                                code="ANALYZER_FAILED",
                                severity=Severity.ERROR,
                                message=failed[index],
                            )
                        ],
                    )
                )
                continue

            try:
                results.append(processor.finish())
            except Exception as exc:
                results.append(
                    AnalysisResult(
                        analyzer=analyzer.name,
                        findings=[
                            Finding(
                                code="ANALYZER_FAILED",
                                severity=Severity.ERROR,
                                message=str(exc),
                            )
                        ],
                    )
                )

        return results
