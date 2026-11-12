import subprocess
from collections.abc import Iterator
from pathlib import Path

import numpy as np
from numpy.typing import NDArray


class AudioDecodeError(RuntimeError):
    """Raised when audio decoding fails."""


def decode_audio(
    path: Path,
    sample_rate: int = 44100,
    channels: int = 2,
    chunk_frames: int = 65536,
) -> Iterator[NDArray[np.float32]]:
    """Decode audio into interleaved float32 PCM chunks."""
    if sample_rate < 1 or channels < 1 or chunk_frames < 1:
        raise ValueError("Audio decoding parameters must be positive")

    command = [
        "ffmpeg",
        "-hide_banner",
        "-nostdin",
        "-v",
        "error",
        "-xerror",
        "-i",
        str(path),
        "-map",
        "0:a:0",
        "-ar",
        str(sample_rate),
        "-ac",
        str(channels),
        "-f",
        "f32le",
        "-acodec",
        "pcm_f32le",
        "pipe:1",
    ]

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )

    try:
        if process.stdout is None:
            raise AudioDecodeError("FFmpeg stdout unavailable")

        bytes_per_frame = channels * 4
        chunk_size = chunk_frames * bytes_per_frame

        while True:
            data = process.stdout.read(chunk_size)

            if not data:
                break

            if len(data) % bytes_per_frame != 0:
                raise AudioDecodeError("Incomplete PCM frame received")

            samples = np.frombuffer(
                data,
                dtype="<f4",
            ).reshape(-1, channels)

            yield samples

        returncode = process.wait()

        if returncode != 0:
            raise AudioDecodeError(f"FFmpeg exited with code {returncode}: {path}")

    finally:
        if process.poll() is None:
            process.kill()

        process.wait()

        if process.stdout is not None:
            process.stdout.close()
