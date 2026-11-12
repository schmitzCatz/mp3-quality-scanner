from pathlib import Path


def discover_mp3_files(directory: Path) -> list[Path]:
    """Discover MP3 files recursively."""
    return sorted(
        path for path in directory.rglob("*") if path.is_file() and path.suffix.lower() == ".mp3"
    )
