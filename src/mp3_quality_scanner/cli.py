from importlib.metadata import version
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from mp3_quality_scanner.config import settings
from mp3_quality_scanner.discovery import discover_mp3_files

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
) -> None:
    """Discover MP3 files recursively."""
    files = discover_mp3_files(path)

    console.print(f"[green]Found {len(files)} MP3 files[/green]")
    console.print(f"Output directory: {settings.output_dir}")

    for file in files:
        console.print(file.relative_to(path))


@app.command()
def version_command() -> None:
    """Display application version."""
    console.print(version("mp3-quality-scanner"))
