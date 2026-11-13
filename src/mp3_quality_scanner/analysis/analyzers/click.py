import numpy as np
from numpy.typing import NDArray
from scipy.ndimage import median_filter

from mp3_quality_scanner.analysis.analyzers.streaming import (
    AudioProcessor,
    PCMChunk,
    StreamingAnalyzer,
)
from mp3_quality_scanner.domain.models import (
    AnalysisResult,
    Finding,
    Severity,
)


class ClickProcessor(AudioProcessor):
    """Detect impulsive artifacts across PCM chunk boundaries."""

    SAMPLE_RATE = 44100
    CHANNELS = 2

    WINDOW_SIZE = 101
    MIN_ABSOLUTE_RESIDUAL = 0.12
    MIN_RELATIVE_CONTRAST = 12.0
    MIN_EVENT_DISTANCE_SECONDS = 0.02
    MAX_FINDINGS = 100

    def __init__(self) -> None:
        self.context = self.WINDOW_SIZE + 1

        self.buffer = np.empty(
            (0, self.CHANNELS),
            dtype=np.float32,
        )

        self.buffer_start = 0
        self.next_frame = 0
        self.total_frames = 0

        self.last_event_frame = -(10**18)
        self.min_distance_frames = round(self.MIN_EVENT_DISTANCE_SECONDS * self.SAMPLE_RATE)

        self.findings: list[Finding] = []
        self.suppressed_findings = 0

    def process(self, chunk: PCMChunk) -> None:
        if chunk.size == 0:
            return

        if chunk.ndim != 2 or chunk.shape[1] != self.CHANNELS:
            raise ValueError("Unexpected PCM channel layout")

        if not np.all(np.isfinite(chunk)):
            raise ValueError("Non-finite PCM samples")

        self.buffer = np.concatenate(
            (self.buffer, chunk),
            axis=0,
        )

        self.total_frames += len(chunk)

        # Keep right context for the next chunk.
        valid_end = self.total_frames - self.context

        if valid_end <= self.next_frame:
            return

        self._process_candidates(
            valid_start=self.next_frame,
            valid_end=valid_end,
        )

        self.next_frame = valid_end

        # Retain left context only.
        keep_from = max(
            self.buffer_start,
            self.next_frame - self.context,
        )

        self.buffer = self.buffer[keep_from - self.buffer_start :].copy()

        self.buffer_start = keep_from

    def finish(self) -> AnalysisResult:
        # Flush remaining frames at end of stream.
        if self.total_frames > self.next_frame:
            self._process_candidates(
                valid_start=self.next_frame,
                valid_end=self.total_frames,
            )

            self.next_frame = self.total_frames

        findings = list(self.findings)

        if self.suppressed_findings:
            findings.append(
                Finding(
                    code="CLICK_FINDINGS_TRUNCATED",
                    severity=Severity.INFO,
                    message=(
                        f"{self.suppressed_findings} additional "
                        "click candidates omitted from report"
                    ),
                )
            )

        return AnalysisResult(
            analyzer="click",
            findings=findings,
        )

    def _process_candidates(
        self,
        valid_start: int,
        valid_end: int,
    ) -> None:
        candidates = self._detect_candidates(self.buffer)

        for local_frame, score in candidates:
            global_frame = self.buffer_start + local_frame

            if not (valid_start <= global_frame < valid_end):
                continue

            if global_frame - self.last_event_frame < self.min_distance_frames:
                continue

            self.last_event_frame = global_frame

            if len(self.findings) >= self.MAX_FINDINGS:
                self.suppressed_findings += 1
                continue

            self.findings.append(
                Finding(
                    code="POSSIBLE_CLICK",
                    severity=Severity.WARNING,
                    message=(f"Possible impulsive artifact (contrast={score:.1f})"),
                    position_seconds=round(
                        global_frame / self.SAMPLE_RATE,
                        3,
                    ),
                )
            )

    def _detect_candidates(
        self,
        samples: NDArray[np.float32],
    ) -> list[tuple[int, float]]:
        if len(samples) < self.WINDOW_SIZE:
            return []

        residual = np.zeros_like(samples)

        residual[1:-1] = samples[1:-1] - 0.5 * (samples[:-2] + samples[2:])

        magnitude = np.abs(residual)

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

        local_scale = 1.4826 * local_mad + 1e-6
        contrast = magnitude / local_scale

        mask = (magnitude >= self.MIN_ABSOLUTE_RESIDUAL) & (contrast >= self.MIN_RELATIVE_CONTRAST)

        mask[0] = False
        mask[-1] = False

        frames, channels = np.nonzero(mask)

        scores: dict[int, float] = {}

        for frame, channel in zip(
            frames,
            channels,
            strict=True,
        ):
            index = int(frame)
            score = float(contrast[frame, channel])

            scores[index] = max(
                scores.get(index, 0.0),
                score,
            )

        return sorted(scores.items())


class ClickAnalyzer(StreamingAnalyzer):
    """Detect possible clicks in decoded audio."""

    @property
    def name(self) -> str:
        return "click"

    @property
    def version(self) -> str:
        return "3"

    def create_processor(self) -> AudioProcessor:
        return ClickProcessor()
