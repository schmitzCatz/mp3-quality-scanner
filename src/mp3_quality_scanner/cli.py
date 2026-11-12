from importlib.metadata import version
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from mp3_quality_scanner.config import settings
from mp3_quality_scanner.toolchain import ToolchainError, check_toolchain

app = typer.Typer(
    name="mp3qs",
    help="Automated MP3 quality and integrity scanner.",
    no_args_is_help=True,
)

console = Console()


@app.command()
def scan(
    path: Annotated[
        Path,
        typer.Argument(
            help="Directory containing MP3 files",
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
        ),
    ],
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Output CSV report path",
        ),
    ] = None,
) -> None:
    """Analyze MP3 files recursively."""
    from mp3_quality_scanner.analyzers.integrity import IntegrityAnalyzer
    from mp3_quality_scanner.reporting.csv_report import write_csv
    from mp3_quality_scanner.scanner import ScanRunner

    report_path = output or settings.output_dir / "scan.csv"

    runner = ScanRunner(
        analyzers=[
            IntegrityAnalyzer(),
        ]
    )

    try:
        check_toolchain()
    except ToolchainError as exc:
        console.print(f"[red]Toolchain error: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    console.print(f"Scanning: {path}")

    results = runner.scan_directory(path)
    write_csv(results, report_path)

    errors = sum(result.status == "error" for result in results)
    warnings = sum(result.status == "warning" for result in results)

    console.print(f"[green]Scanned: {len(results)} files[/green]")
    console.print(f"[red]Errors: {errors}[/red]")
    console.print(f"[yellow]Warnings: {warnings}[/yellow]")
    console.print(f"Report: {report_path}")


@app.command()
def doctor() -> None:
    """Check required external dependencies."""
    console.print("[bold]Checking audio toolchain...[/bold]")

    try:
        tools = check_toolchain()
    except ToolchainError as exc:
        console.print(f"[red]ERROR: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    for tool in tools:
        console.print(f"[green]OK[/green] {tool.name}")
        console.print(f"  Path: {tool.path}")
        console.print(f"  Version: {tool.version}")

    console.print("[green]All required tools available.[/green]")


@app.command()
def version_command() -> None:
    """Display application version."""
    console.print(version("mp3-quality-scanner"))
