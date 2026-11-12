from pathlib import Path

from mp3_quality_scanner.discovery import discover_mp3_files


def test_discover_mp3_files_recursively(tmp_path: Path) -> None:
    album = tmp_path / "album"
    album.mkdir()

    (album / "track01.mp3").touch()
    (album / "track02.MP3").touch()
    (album / "cover.jpg").touch()

    files = discover_mp3_files(tmp_path)

    assert len(files) == 2
    assert all(file.suffix.lower() == ".mp3" for file in files)


def test_empty_directory(tmp_path: Path) -> None:
    assert discover_mp3_files(tmp_path) == []
