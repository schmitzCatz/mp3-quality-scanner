from dataclasses import dataclass
from pathlib import Path

from mutagen.id3 import ID3, ID3NoHeaderError


@dataclass(frozen=True)
class TrackTags:
    title: str | None = None
    album: str | None = None
    artist: str | None = None
    track_number: int | None = None
    disc_number: int | None = None


def _number(value: str | None) -> int | None:
    if not value:
        return None

    try:
        return int(value.split("/", 1)[0])
    except ValueError:
        return None


def read_track_tags(path: Path) -> TrackTags:
    try:
        tags = ID3(path)  # type: ignore[no-untyped-call]
    except ID3NoHeaderError:
        return TrackTags()

    def get_text(key: str) -> str | None:
        frame = tags.get(key)  # type: ignore[no-untyped-call]

        if frame is None:
            return None

        value = str(frame).strip()
        return value or None

    return TrackTags(
        title=get_text("TIT2"),
        album=get_text("TALB"),
        artist=get_text("TPE1"),
        track_number=_number(get_text("TRCK")),
        disc_number=_number(get_text("TPOS")),
    )
