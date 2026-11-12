from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from scipy.ndimage import median_filter

from mp3_quality_scanner.analyzers.base import Analyzer
from mp3_quality_scanner.audio import decode_audio
from mp3_quality_scanner.models import (
    AnalysisResult,
    Finding,
    Severity,
)


class ClickAnalyzer(Analyzer):
    """Detect isolated impulsive artifacts in decoded audio."""

    SAMPLE_RATE = 22050
    CHANNELS = 2

    WINDOW_SIZE = 101
    MIN_ABSOLUTE_RESIDUAL = 0.12
    MIN_RELATIVE_CONTRAST = 12.0
    MAX_FINDINGS = 100
    MIN_EVENT_DISTANCE_SECONDS = 0.02

    @property
    def name(self) -> str:
        return "click"

    @property
    def version(self) -> str:
        return "1"

    def analyze(self, path: Path) -> AnalysisResult:
        findings: list[Finding] = []

        # Retain a small overlap so that clicks crossing
        # PCM chunk boundaries can still be detected.
        overlap_frames = self.WINDOW_SIZE
        previous_tail: NDArray[np.float32] | None = None

        processed_frames = 0
        last_event_seconds = float("-inf")

        for chunk in decode_audio(
            path,
            sample_rate=self.SAMPLE_RATE,
            channels=self.CHANNELS,
        ):
            if chunk.size == 0:
                continue

            if previous_tail is not None:
                samples = np.concatenate(
                    (previous_tail, chunk),
                    axis=0,
                )
                offset = processed_frames - len(previous_tail)
            else:
                samples = chunk
                offset = processed_frames

            candidates = self._detect_candidates(samples)

            for frame_index, score in candidates:
                global_frame = offset + frame_index
                position_seconds = global_frame / self.SAMPLE_RATE

                # Suppress repeated detections from the same
                # short impulse.
                if position_seconds - last_event_seconds < self.MIN_EVENT_DISTANCE_SECONDS:
                    continue

                findings.append(
                    Finding(
                        code="POSSIBLE_CLICK",
                        severity=Severity.WARNING,
                        message=(f"Possible impulsive artifact (contrast={score:.1f})"),
                        position_seconds=round(
                            position_seconds,
                            3,
                        ),
                    )
                )

                last_event_seconds = position_seconds

                if len(findings) >= self.MAX_FINDINGS:
                    break

            processed_frames += len(chunk)

            previous_tail = samples[-overlap_frames:].copy()

            if len(findings) >= self.MAX_FINDINGS:
                break

        return AnalysisResult(
            analyzer=self.name,
            findings=findings,
        )

    def _detect_candidates(
        self,
        samples: NDArray[np.float32],
    ) -> list[tuple[int, float]]:
        """Find isolated sample discontinuities."""

        if len(samples) < self.WINDOW_SIZE:
            return []

        # Residual against linear interpolation of neighbors.
        residual = np.zeros_like(samples)

        residual[1:-1] = samples[1:-1] - 0.5 * (samples[:-2] + samples[2:])

        magnitude = np.abs(residual)

        # Local robust noise estimate.
        local_median = median_filter(
            magnitude,
            size=(self.WINDOW_SIZE, 1),
            mode="reflect",
        )

        deviation = np.abs(magnitude - local_median)

        local_mad = median_filter(
            deviation,
            size=(self.WINDOW_SIZE, 1),
            mode="reflect",
        )

        # Robust local scale estimate.
        local_scale = 1.4826 * local_mad + 1e-6

        contrast = magnitude / local_scale

        candidates_mask = (magnitude >= self.MIN_ABSOLUTE_RESIDUAL) & (
            contrast >= self.MIN_RELATIVE_CONTRAST
        )

        # Ignore the boundary samples where the residual
        # cannot be computed correctly.
        candidates_mask[0] = False
        candidates_mask[-1] = False

        frames, channels = np.nonzero(candidates_mask)

        if frames.size == 0:
            return []

        # Combine channels by frame, retaining the strongest
        # candidate score.
        scores: dict[int, float] = {}

        for frame, channel in zip(
            frames,
            channels,
            strict=True,
        ):
            frame_index = int(frame)
            score = float(contrast[frame, channel])

            scores[frame_index] = max(
                scores.get(frame_index, 0.0),
                score,
            )

        return sorted(scores.items())
