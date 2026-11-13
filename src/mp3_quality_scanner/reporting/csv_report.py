import csv
from pathlib import Path

from mp3_quality_scanner.domain.models import ScanResult


def write_csv(results: list[ScanResult], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)

        writer.writerow(
            [
                "file",
                "status",
                "analyzer",
                "code",
                "severity",
                "message",
                "position_seconds",
            ]
        )

        for result in results:
            if not result.findings:
                writer.writerow(
                    [
                        str(result.path),
                        result.status,
                        "",
                        "",
                        "",
                        "",
                        "",
                    ]
                )
                continue

            for analysis in result.analyses:
                for finding in analysis.findings:
                    writer.writerow(
                        [
                            str(result.path),
                            result.status,
                            analysis.analyzer,
                            finding.code,
                            finding.severity.value,
                            finding.message,
                            finding.position_seconds
                            if finding.position_seconds is not None
                            else "",
                        ]
                    )
