from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from mp3_quality_scanner.persistence.repository import (
    QualityFile,
    QualitySummary,
    ScanRepository,
)


def render_quality_report(
    repository: ScanRepository,
    console: Console | None = None,
    limit: int = 20,
) -> None:
    console = console or Console()

    summary = repository.get_quality_summary()
    worst_files = repository.get_worst_files(limit=limit)

    _render_summary(console, summary)
    _render_worst_files(console, worst_files)


def _render_summary(
    console: Console,
    summary: QualitySummary,
) -> None:
    console.print()
    console.print(
        Panel(
            f"Files in database: [bold]{summary.total}[/bold]",
            title="MP3 Quality Scanner",
            expand=False,
        )
    )

    table = Table(
        title="Quality Overview",
        show_header=True,
    )

    table.add_column("Critical", justify="right")
    table.add_column("Review", justify="right")
    table.add_column("Good", justify="right")
    table.add_column("Unknown", justify="right")

    table.add_row(
        f"[red]{summary.critical}[/red]",
        f"[yellow]{summary.review}[/yellow]",
        f"[green]{summary.good}[/green]",
        str(summary.unknown),
    )

    console.print(table)


def _render_worst_files(
    console: Console,
    files: list[QualityFile],
) -> None:
    console.print()

    if not files:
        console.print("[dim]No scored files available.[/dim]")
        return

    table = Table(
        title="Most Suspicious Files",
        show_lines=False,
    )
    table.add_column(
        "Score",
        justify="right",
        style="bold",
    )
    table.add_column(
        "File",
        overflow="fold",
    )
    table.add_column(
        "Findings",
        justify="right",
    )
    table.add_column(
        "Clicks",
        justify="right",
    )
    table.add_column("Clicks/min", justify="right")

    for file in files:
        score = file.score

        if score is None:
            score_text = "-"
        elif score < 50:
            score_text = f"[red]{score}[/red]"
        elif score < 80:
            score_text = f"[yellow]{score}[/yellow]"
        else:
            score_text = f"[green]{score}[/green]"

        table.add_row(
            score_text,
            file.path,
            str(file.finding_count),
            str(file.click_count),
            (f"{file.click_rate:.2f}" if file.click_rate is not None else "-"),
        )

    console.print(table)
