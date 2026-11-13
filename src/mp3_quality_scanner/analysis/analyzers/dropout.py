from collections import deque
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from mp3_quality_scanner.analysis.analyzers.streaming import (
    AudioProcessor,
    StreamingAnalyzer,
)
from mp3_quality_scanner.domain.models import (
    AnalysisResult,
    Finding,
    Severity,
)

PCMChunk = NDArray[np.float32]


@dataclass
class DropoutCandidate:
    start_frame: int
    duration_frames: int
    before_rms: float
    after_samples: list[float]


class DropoutProcessor(AudioProcessor):
    SAMPLE_RATE = 44100

    SILENCE_THRESHOLD = 10 ** (-60 / 20)
    CONTEXT_THRESHOLD = 10 ** (-35 / 20)

    MIN_DURATION_MS = 10
    MAX_DURATION_MS = 250
    CONTEXT_MS = 20

    MAX_FINDINGS = 100

    def __init__(self) -> None:
        self.min_frames = round(self.SAMPLE_RATE * self.MIN_DURATION_MS / 1000)
        self.max_frames = round(self.SAMPLE_RATE * self.MAX_DURATION_MS / 1000)
        self.context_frames = round(self.SAMPLE_RATE * self.CONTEXT_MS / 1000)

        self.position = 0

        self.history: deque[float] = deque(maxlen=self.context_frames)

        self.silence_start: int | None = None
        self.silence_frames = 0
        self.before_rms = 0.0

        self.pending: DropoutCandidate | None = None

        self.findings: list[Finding] = []
        self.truncated = False

        self.in_long_silence = False

    @staticmethod
    def _rms(values: list[float]) -> float:
        if not values:
            return 0.0

        samples = np.asarray(values, dtype=np.float64)
        return float(np.sqrt(np.mean(samples * samples)))

    def _emit(self, candidate: DropoutCandidate) -> None:
        after_rms = self._rms(candidate.after_samples)

        if candidate.before_rms < self.CONTEXT_THRESHOLD or after_rms < self.CONTEXT_THRESHOLD:
            return

        if len(self.findings) >= self.MAX_FINDINGS:
            self.truncated = True
            return

        duration_ms = candidate.duration_frames * 1000 / self.SAMPLE_RATE

        self.findings.append(
            Finding(
                code="POSSIBLE_DROPOUT",
                severity=Severity.WARNING,
                message=(f"Possible audio dropout ({duration_ms:.1f} ms)"),
                position_seconds=(candidate.start_frame / self.SAMPLE_RATE),
            )
        )

    def _process_level(self, level: float) -> None:
        is_silent = level <= self.SILENCE_THRESHOLD

        # Ignore long silence until the signal returns.
        if self.in_long_silence:
            if not is_silent:
                self.in_long_silence = False
                self.history.clear()
                self.history.append(level)

            self.position += 1
            return

        # Collect context after a possible dropout.
        if self.pending is not None:
            self.pending.after_samples.append(level)

            if len(self.pending.after_samples) >= self.context_frames:
                self._emit(self.pending)
                self.pending = None

        # Continue an active silence interval.
        if self.silence_start is not None:
            if is_silent:
                self.silence_frames += 1

                # A long silence is not a short dropout.
                if self.silence_frames > self.max_frames:
                    self.silence_start = None
                    self.silence_frames = 0
                    self.before_rms = 0.0

                    self.in_long_silence = True

                    # Do not use samples from before
                    # the long silence as context.
                    self.history.clear()

                self.position += 1
                return

            # Silence has ended.
            if self.min_frames <= self.silence_frames <= self.max_frames:
                self.pending = DropoutCandidate(
                    start_frame=self.silence_start,
                    duration_frames=self.silence_frames,
                    before_rms=self.before_rms,
                    after_samples=[level],
                )

            self.silence_start = None
            self.silence_frames = 0
            self.before_rms = 0.0

            self.history.clear()
            self.history.append(level)

            self.position += 1
            return

        # Start a new silence interval.
        if is_silent:
            self.silence_start = self.position
            self.silence_frames = 1
            self.before_rms = self._rms(list(self.history))

        else:
            self.history.append(level)

        self.position += 1

    def process(self, chunk: PCMChunk) -> None:
        if chunk.ndim != 2:
            raise ValueError("Expected 2D PCM chunk")

        if not np.isfinite(chunk).all():
            raise ValueError("PCM contains non-finite samples")

        # Require all channels to be quiet.
        levels = np.max(
            np.abs(chunk),
            axis=1,
        )

        for level in levels:
            self._process_level(float(level))

    def finish(self) -> AnalysisResult:
        if self.truncated:
            self.findings.append(
                Finding(
                    code="DROPOUT_FINDINGS_TRUNCATED",
                    severity=Severity.INFO,
                    message="Dropout findings limit reached",
                )
            )

        return AnalysisResult(
            analyzer="dropout",
            findings=self.findings,
        )


class DropoutAnalyzer(StreamingAnalyzer):
    @property
    def name(self) -> str:
        return "dropout"

    @property
    def version(self) -> str:
        return "1"

    def create_processor(self) -> AudioProcessor:
        return DropoutProcessor()
