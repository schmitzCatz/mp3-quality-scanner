"""Deterministic synthetic PCM signals for click-detector evaluation."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

SAMPLE_RATE = 44_100


@dataclass(frozen=True)
class Scenario:
    name: str
    samples: NDArray[np.float32]
    click_frames: tuple[int, ...] = ()


def _stereo(mono: NDArray[np.float32]) -> NDArray[np.float32]:
    return np.column_stack((mono, mono)).astype(np.float32)


def scenarios(seconds: float = 2.0, seed: int = 2026) -> list[Scenario]:
    """Return clean and corrupted signals with known event positions."""
    rng = np.random.default_rng(seed)
    n = int(SAMPLE_RATE * seconds)
    t = np.arange(n, dtype=np.float64) / SAMPLE_RATE

    silence = np.zeros(n, dtype=np.float32)
    sine = (0.55 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    noise = rng.normal(0, 0.08, n).astype(np.float32)
    noise = np.clip(noise, -1.0, 1.0)

    # A damped sinusoid is a deliberately sharp but legitimate transient.
    percussion = np.zeros(n, dtype=np.float32)
    for onset in np.arange(0.25, seconds - 0.1, 0.4):
        start = int(onset * SAMPLE_RATE)
        length = min(int(0.12 * SAMPLE_RATE), n - start)
        local_t = np.arange(length) / SAMPLE_RATE
        hit = 0.8 * np.exp(-local_t * 65) * np.sin(2 * np.pi * 180 * local_t)
        percussion[start : start + length] += hit.astype(np.float32)

    # Smooth saturated waveform; high amplitude alone is not a click.
    compressed = np.tanh(4.0 * sine).astype(np.float32)

    click_frames = tuple(int(s * SAMPLE_RATE) for s in (0.35, 0.95, 1.55) if s < seconds - 0.1)
    injected = sine.copy()
    for frame in click_frames:
        injected[frame] = np.float32(-0.95 if injected[frame] > 0 else 0.95)

    # A 3-sample burst to exercise detection beyond a single-sample spike.
    burst = sine.copy()
    burst_frame = int(1.1 * SAMPLE_RATE)
    if burst_frame + 3 < n:
        burst[burst_frame : burst_frame + 3] = [0.95, -0.95, 0.95]
        burst_events = (burst_frame,)
    else:
        burst_events = ()

    return [
        Scenario("silence", _stereo(silence)),
        Scenario("sine", _stereo(sine)),
        Scenario("noise", _stereo(noise)),
        Scenario("percussion", _stereo(percussion)),
        Scenario("compressed", _stereo(compressed)),
        Scenario("injected_clicks", _stereo(injected), click_frames),
        Scenario("short_burst", _stereo(burst), burst_events),
    ]
