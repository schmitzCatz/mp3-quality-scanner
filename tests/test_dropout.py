import numpy as np
import pytest

from mp3_quality_scanner.analysis.analyzers.dropout import DropoutProcessor

SAMPLE_RATE = 44100


def make_audio(
    duration_seconds: float = 2.0,
    frequency: float = 440.0,
) -> np.ndarray:
    t = np.arange(int(duration_seconds * SAMPLE_RATE)) / SAMPLE_RATE

    signal = (0.5 * np.sin(2 * np.pi * frequency * t)).astype(np.float32)

    return np.column_stack((signal, signal))


def analyze(
    audio: np.ndarray,
    chunk_frames: int = 65536,
) -> list[str]:
    processor = DropoutProcessor()

    for start in range(0, len(audio), chunk_frames):
        processor.process(audio[start : start + chunk_frames])

    return [finding.code for finding in processor.finish().findings]


def test_clean_signal_has_no_dropout() -> None:
    audio = make_audio()

    assert "POSSIBLE_DROPOUT" not in analyze(audio)


def test_detects_short_dropout() -> None:
    audio = make_audio()

    start = int(0.8 * SAMPLE_RATE)
    duration = int(0.05 * SAMPLE_RATE)

    audio[start : start + duration] = 0.0

    assert "POSSIBLE_DROPOUT" in analyze(audio)


def test_ignores_very_short_silence() -> None:
    audio = make_audio()

    start = int(0.8 * SAMPLE_RATE)
    duration = int(0.005 * SAMPLE_RATE)

    audio[start : start + duration] = 0.0

    assert "POSSIBLE_DROPOUT" not in analyze(audio)


def test_ignores_long_silence() -> None:
    audio = make_audio()

    start = int(0.8 * SAMPLE_RATE)
    duration = int(0.5 * SAMPLE_RATE)

    audio[start : start + duration] = 0.0

    assert "POSSIBLE_DROPOUT" not in analyze(audio)


def test_detects_dropout_across_chunk_boundary() -> None:
    audio = make_audio()

    boundary = 4096
    start = boundary - 100
    duration = int(0.04 * SAMPLE_RATE)

    audio[start : start + duration] = 0.0

    assert "POSSIBLE_DROPOUT" in analyze(
        audio,
        chunk_frames=boundary,
    )


def test_ignores_silence_at_start() -> None:
    audio = make_audio()
    audio[: int(0.05 * SAMPLE_RATE)] = 0.0

    assert "POSSIBLE_DROPOUT" not in analyze(audio)


def test_ignores_silence_at_end() -> None:
    audio = make_audio()
    audio[-int(0.05 * SAMPLE_RATE) :] = 0.0

    assert "POSSIBLE_DROPOUT" not in analyze(audio)


def test_rejects_invalid_pcm_shape() -> None:
    processor = DropoutProcessor()

    with pytest.raises(ValueError):
        processor.process(np.zeros(100, dtype=np.float32))


def test_rejects_nonfinite_pcm() -> None:
    processor = DropoutProcessor()

    audio = np.zeros((100, 2), dtype=np.float32)
    audio[10, 0] = np.nan

    with pytest.raises(ValueError):
        processor.process(audio)


def test_ignores_long_silence_across_chunks() -> None:
    audio = make_audio()

    start = int(0.5 * SAMPLE_RATE)
    duration = int(0.8 * SAMPLE_RATE)

    audio[start : start + duration] = 0.0

    assert "POSSIBLE_DROPOUT" not in analyze(
        audio,
        chunk_frames=1024,
    )


def test_detects_dropout_after_long_silence() -> None:
    audio = make_audio(duration_seconds=3.0)

    audio[int(0.5 * SAMPLE_RATE) : int(1.0 * SAMPLE_RATE)] = 0.0

    audio[int(2.0 * SAMPLE_RATE) : int(2.05 * SAMPLE_RATE)] = 0.0

    codes = analyze(audio, chunk_frames=1024)

    assert codes.count("POSSIBLE_DROPOUT") == 1
