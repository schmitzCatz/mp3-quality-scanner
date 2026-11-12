
from pathlib import Path

import numpy as np

from mp3_quality_scanner.analyzers.base import Analyzer
from mp3_quality_scanner.audio import decode_audio
from mp3_quality_scanner.models import (
    AnalysisResult,
    Finding,
    Severity,
)
from mp3_quality_scanner.signal import RunTracker


class ClippingAnalyzer(Analyzer):
    """Detect potential clipping in decoded audio signals.

    Analyzes PCM samples for:
    - Samples close to or above full scale
    - Sustained runs of near-full-scale samples
    - Invalid or empty audio signals

    Note:
        These are clipping indicators, not definitive proof
        of audible distortion.
    """

    THRESHOLD = 0.999
    MIN_CLIPPING_RATIO = 0.001
    MIN_CONSECUTIVE_SAMPLES = 8

    @property
    def name(self) -> str:
        return "clipping"

    @property
    def version(self) -> str:
        return "2"

    def analyze(self, path: Path) -> AnalysisResult:
        """Analyze an MP3 file for potential clipping."""

        total_samples = 0
        clipped_samples = 0
        peak = 0.0
        sum_squares = 0.0

        run_tracker: RunTracker | None = None

        for chunk in decode_audio(path):
            if chunk.size == 0:
                continue

            # Calculate absolute sample amplitudes.
            absolute = np.abs(chunk)

            # Identify samples close to full scale.
            clipped = absolute >= self.THRESHOLD

            total_samples += chunk.size
            clipped_samples += int(np.count_nonzero(clipped))

            # Calculate peak amplitude.
            peak = max(
                peak,
                float(np.max(absolute)),
            )

            # Accumulate squared amplitudes using float64
            # to avoid numerical precision issues.
            sum_squares += float(
                np.sum(
                    np.square(chunk, dtype=np.float64)
                )
            )

            # Track consecutive clipped samples per channel,
            # including runs crossing chunk boundaries.
            if run_tracker is None:
                run_tracker = RunTracker(
                    channels=chunk.shape[1]
                )

            run_tracker.update(clipped)

        findings: list[Finding] = []

        # Handle empty or undecodable audio.
        if total_samples == 0:
            findings.append(
                Finding(
                    code="EMPTY_AUDIO",
                    severity=Severity.ERROR,
                    message="No audio samples decoded",
                )
            )

            return AnalysisResult(
                analyzer=self.name,
                findings=findings,
            )

        # Calculate signal metrics.
        clipping_ratio = clipped_samples / total_samples
        rms = (sum_squares / total_samples) ** 0.5

        longest_run = (
            run_tracker.longest
            if run_tracker is not None
            else 0
        )

        # Detect excessive clipping.
        if clipping_ratio >= self.MIN_CLIPPING_RATIO:
            findings.append(
                Finding(
                    code="HIGH_CLIPPING_RATIO",
                    severity=Severity.WARNING,
                    message=(
                        f"Clipping ratio: {clipping_ratio:.4%}, "
                        f"peak: {peak:.4f}"
                    ),
                )
            )

        # Detect sustained clipping.
        if longest_run >= self.MIN_CONSECUTIVE_SAMPLES:
            findings.append(
                Finding(
                    code="SUSTAINED_CLIPPING",
                    severity=Severity.WARNING,
                    message=(
                        "Longest near-full-scale run: "
                        f"{longest_run} samples"
                    ),
                )
            )

        # Detect invalid PCM values.
        if not np.isfinite(rms) or not np.isfinite(peak):
            findings.append(
                Finding(
                    code="INVALID_PCM",
                    severity=Severity.ERROR,
                    message="Non-finite PCM values detected",
                )
            )

        return AnalysisResult(
            analyzer=self.name,
            findings=findings,
        )
