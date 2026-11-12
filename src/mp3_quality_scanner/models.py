from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class Finding:
    code: str
    severity: Severity
    message: str
    position_seconds: float | None = None


@dataclass(frozen=True)
class AudioMetadata:
    codec: str
    duration_seconds: float | None
    bitrate: int | None
    sample_rate: int | None
    channels: int | None


@dataclass
class AnalysisResult:
    analyzer: str
    findings: list[Finding] = field(default_factory=list)
    metadata: AudioMetadata | None = None


@dataclass
class ScanResult:
    path: Path
    analyses: list[AnalysisResult] = field(default_factory=list)

    @property
    def findings(self) -> list[Finding]:
        return [finding for analysis in self.analyses for finding in analysis.findings]

    @property
    def status(self) -> str:
        if any(f.severity == Severity.ERROR for f in self.findings):
            return "error"

        if any(f.severity == Severity.WARNING for f in self.findings):
            return "warning"

        return "ok"
