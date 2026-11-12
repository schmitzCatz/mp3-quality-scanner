from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from mp3_quality_scanner.analyzers.base import Analyzer
from mp3_quality_scanner.audio import decode_audio
from mp3_quality_scanner.models import AnalysisResult

PCMChunk = NDArray[np.float32]


class AudioProcessor(ABC):
    """Stateful processor consuming decoded PCM chunks."""

    @abstractmethod
    def process(self, chunk: PCMChunk) -> None:
        """Process the next chunk."""

    @abstractmethod
    def finish(self) -> AnalysisResult:
        """Return the completed analysis."""


class StreamingAnalyzer(Analyzer, ABC):
    """Analyzer supporting shared PCM decoding."""

    @abstractmethod
    def create_processor(self) -> AudioProcessor:
        """Create independent state for one audio file."""

    def analyze(self, path: Path) -> AnalysisResult:
        """Standalone compatibility with the Analyzer API."""
        processor = self.create_processor()

        for chunk in decode_audio(
            path,
            sample_rate=44100,
            channels=2,
        ):
            processor.process(chunk)

        return processor.finish()
