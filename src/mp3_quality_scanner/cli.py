from importlib.metadata import version
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from mp3_quality_scanner.analyzers.clipping import ClippingAnalyzer
from mp3_quality_scanner.config import settings
from mp3_quality_scanner.progress import ScanProgress
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
    database: Annotated[
        Path | None,
        typer.Option("--database", "-d"),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o"),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", help="Reanalyze all files"),
    ] = False,
    workers: Annotated[
        int | None,
        typer.Option("--workers", "-w"),
    ] = None,
) -> None:
    """Scan MP3 files and persist analysis results."""
    from mp3_quality_scanner.analyzers.integrity import IntegrityAnalyzer
    from mp3_quality_scanner.repository import ScanRepository
    from mp3_quality_scanner.scanner import ScanRunner
    from mp3_quality_scanner.toolchain import (
        ToolchainError,
        check_toolchain,
    )

    try:
        check_toolchain()
    except ToolchainError as exc:
        console.print(f"[red]Toolchain error: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    database_path = database or settings.output_dir / "scan.db"
    report_path = output or settings.output_dir / "scan.csv"

    runner = ScanRunner(analyzers=[IntegrityAnalyzer(), ClippingAnalyzer()])

    with ScanRepository(database_path) as repository:
        with ScanProgress(console) as progress:
            stats = runner.scan_directory(
                directory=path,
                repository=repository,
                force=force,
                workers=workers or settings.workers,
                callback=progress.on_event,
            )

        repository.export_csv(report_path)

    console.print()
    console.print("[bold]Scan completed[/bold]")
    console.print(f"Discovered: {stats.discovered}")
    console.print(f"Analyzed:   {stats.analyzed}")
    console.print(f"Skipped:    {stats.skipped}")
    console.print(f"Errors:     {stats.errors}")
    console.print(f"Warnings:   {stats.warnings}")
    console.print(f"Database:   {database_path}")
    console.print(f"Report:     {report_path}")


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
