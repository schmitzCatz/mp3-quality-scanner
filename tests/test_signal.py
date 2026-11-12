
import numpy as np

from mp3_quality_scanner.signal import (
    RunTracker,
    longest_true_run,
)


def test_longest_true_run() -> None:
    values = np.array(
        [False, True, True, False, True, True, True]
    )

    assert longest_true_run(values) == 3


def test_no_true_values() -> None:
    values = np.array([False, False, False])

    assert longest_true_run(values) == 0


def test_run_across_chunk_boundary() -> None:
    tracker = RunTracker(channels=2)

    first = np.array(
        [
            [False, False],
            [True, False],
            [True, False],
        ]
    )

    second = np.array(
        [
            [True, False],
            [True, False],
            [False, False],
        ]
    )

    tracker.update(first)
    tracker.update(second)

    assert tracker.longest == 4


def test_all_true_across_multiple_chunks() -> None:
    tracker = RunTracker(channels=1)

    tracker.update(np.ones((10, 1), dtype=np.bool_))
    tracker.update(np.ones((20, 1), dtype=np.bool_))

    assert tracker.longest == 30
