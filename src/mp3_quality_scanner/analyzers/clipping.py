import numpy as np

from mp3_quality_scanner.analyzers.streaming import (
    AudioProcessor,
    PCMChunk,
    StreamingAnalyzer,
)
from mp3_quality_scanner.models import (
    AnalysisResult,
    Finding,
    Severity,
)
from mp3_quality_scanner.signal import RunTracker


class ClippingProcessor(AudioProcessor):
    """Accumulate clipping metrics from PCM chunks."""

    THRESHOLD = 0.999
    MIN_CLIPPING_RATIO = 0.001
    MIN_CONSECUTIVE_SAMPLES = 8

    def __init__(self) -> None:
        self.total_samples = 0
        self.clipped_samples = 0
        self.peak = 0.0
        self.sum_squares = 0.0
        self.run_tracker: RunTracker | None = None

    def process(self, chunk: PCMChunk) -> None:
        if chunk.size == 0:
            return

        if chunk.ndim != 2:
            raise ValueError("Expected 2D PCM array")

        if not np.all(np.isfinite(chunk)):
            raise ValueError("Non-finite PCM samples")

        absolute = np.abs(chunk)
        clipped = absolute >= self.THRESHOLD

        self.total_samples += chunk.size
        self.clipped_samples += int(np.count_nonzero(clipped))

        self.peak = max(
            self.peak,
            float(np.max(absolute)),
        )

        self.sum_squares += float(np.sum(np.square(chunk, dtype=np.float64)))

        if self.run_tracker is None:
            self.run_tracker = RunTracker(channels=chunk.shape[1])

        self.run_tracker.update(clipped)

    def finish(self) -> AnalysisResult:
        findings: list[Finding] = []

        if self.total_samples == 0:
            findings.append(
                Finding(
                    code="EMPTY_AUDIO",
                    severity=Severity.ERROR,
                    message="No audio samples decoded",
                )
            )

            return AnalysisResult(
                analyzer="clipping",
                findings=findings,
            )

        clipping_ratio = self.clipped_samples / self.total_samples

        longest_run = self.run_tracker.longest if self.run_tracker is not None else 0

        if clipping_ratio >= self.MIN_CLIPPING_RATIO:
            findings.append(
                Finding(
                    code="HIGH_CLIPPING_RATIO",
                    severity=Severity.WARNING,
                    message=(f"Clipping ratio: {clipping_ratio:.4%}, peak: {self.peak:.4f}"),
                )
            )

        if longest_run >= self.MIN_CONSECUTIVE_SAMPLES:
            findings.append(
                Finding(
                    code="SUSTAINED_CLIPPING",
                    severity=Severity.WARNING,
                    message=(f"Longest near-full-scale run: {longest_run} samples"),
                )
            )

        return AnalysisResult(
            analyzer="clipping",
            findings=findings,
        )


class ClippingAnalyzer(StreamingAnalyzer):
    """Detect potential clipping in decoded audio."""

    @property
    def name(self) -> str:
        return "clipping"

    @property
    def version(self) -> str:
        return "3"

    def create_processor(self) -> AudioProcessor:
        return ClippingProcessor()
