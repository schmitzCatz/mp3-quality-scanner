from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray


def longest_true_run(
        values: NDArray[np.bool_],
) -> int:
    """Return the longest consecutive run of True values."""
    if values.size == 0:
        return 0

    padded = np.concatenate(
        (
            np.array([False]),
            values,
            np.array([False]),
        )
    )

    transitions = np.diff(padded.astype(np.int8))

    starts = np.flatnonzero(transitions == 1)
    ends = np.flatnonzero(transitions == -1)

    if starts.size == 0:
        return 0

    return int(np.max(ends - starts))


@dataclass
class RunTracker:
    channels: int
    longest: int = 0
    trailing: NDArray[np.int64] = field(init=False)

    def __post_init__(self) -> None:
        self.trailing = np.zeros(
            self.channels,
            dtype=np.int64,
        )

    def update(
            self,
            clipped: NDArray[np.bool_],
    ) -> None:
        for channel in range(self.channels):
            values = clipped[:, channel]

            if values.size == 0:
                continue

            local_longest = longest_true_run(values)

            first_false = np.flatnonzero(~values)

            if first_false.size == 0:
                prefix = values.size
                suffix = values.size
            else:
                prefix = int(first_false[0])
                suffix = int(values.size - 1 - first_false[-1])

            boundary_run = int(self.trailing[channel]) + prefix

            self.longest = max(
                self.longest,
                local_longest,
                boundary_run,
            )

            if suffix == values.size:
                self.trailing[channel] += suffix
            else:
                self.trailing[channel] = suffix
