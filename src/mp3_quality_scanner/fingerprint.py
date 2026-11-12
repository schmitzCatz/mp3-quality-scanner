import hashlib
import json
from collections.abc import Sequence

from mp3_quality_scanner.analyzers.base import Analyzer


def analyzer_fingerprint(analyzers: Sequence[Analyzer]) -> str:
    """Create a stable fingerprint for an analyzer pipeline."""
    configuration = [
        {
            "name": analyzer.name,
            "version": analyzer.version,
        }
        for analyzer in analyzers
    ]

    serialized = json.dumps(
        configuration,
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
