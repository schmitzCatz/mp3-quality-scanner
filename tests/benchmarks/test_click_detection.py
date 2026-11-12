"""Run with: uv run pytest tests/benchmarks/test_click_detection.py -v -s"""

import pytest

from mp3_quality_scanner.analyzers.click import ClickProcessor
from tests.benchmarks.signals import SAMPLE_RATE, Scenario, scenarios

# Allow 3 ms position tolerance because detection may peak on a neighboring sample.
MATCH_TOLERANCE_FRAMES = round(0.003 * SAMPLE_RATE)


def detect_frames(scenario: Scenario, chunk_size: int = 4096) -> list[int]:
    samples = scenario.samples
    chunks = (samples[i : i + chunk_size] for i in range(0, len(samples), chunk_size))
    processor = ClickProcessor()

    for chunk in chunks:
        processor.process(chunk)

    result = processor.finish()

    return [
        round(finding.position_seconds * SAMPLE_RATE)
        for finding in result.findings
        if finding.code == "POSSIBLE_CLICK" and finding.position_seconds is not None
    ]


def match_events(expected: tuple[int, ...], detected: list[int]) -> tuple[int, int, int]:
    """One-to-one event matching; return TP, FP, FN."""
    unmatched = set(range(len(detected)))
    tp = 0
    for event in expected:
        candidates = [
            index for index in unmatched if abs(detected[index] - event) <= MATCH_TOLERANCE_FRAMES
        ]
        if candidates:
            nearest = min(candidates, key=lambda i: abs(detected[i] - event))
            unmatched.remove(nearest)
            tp += 1
    return tp, len(unmatched), len(expected) - tp


def metrics(tp: int, fp: int, fn: int) -> tuple[float, float]:
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    return precision, recall


@pytest.mark.parametrize("scenario", scenarios(), ids=lambda s: s.name)
def test_benchmark_scenario(scenario: Scenario) -> None:
    detected = detect_frames(scenario)
    tp, fp, fn = match_events(scenario.click_frames, detected)
    precision, recall = metrics(tp, fp, fn)
    duration = len(scenario.samples) / SAMPLE_RATE
    fp_per_minute = fp / duration * 60
    print(
        f"{scenario.name:17s} TP={tp:2d} FP={fp:3d} FN={fn:2d} "
        f"precision={precision:.2f} recall={recall:.2f} "
        f"FP/min={fp_per_minute:.1f}"
    )
    # Benchmark is observational: calibration thresholds come after measurement.
    assert all(0 <= frame < len(scenario.samples) for frame in detected)


def test_known_isolated_click_is_detected() -> None:
    scenario = next(s for s in scenarios() if s.name == "injected_clicks")
    detected = detect_frames(scenario)
    tp, _, _ = match_events(scenario.click_frames, detected)
    assert tp >= 1, "Detector missed every injected click"


def test_silence_does_not_trigger() -> None:
    scenario = next(s for s in scenarios() if s.name == "silence")
    assert detect_frames(scenario) == []


def test_event_matching_is_one_to_one() -> None:
    assert match_events((100,), [99, 101]) == (1, 1, 0)
