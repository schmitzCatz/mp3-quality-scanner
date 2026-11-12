# MP3 Quality Scanner 1.0.0

First stable release candidate of a local MP3 quality assessment tool.

**Highlights:** integrity checks via FFmpeg/FFprobe; clipping, click and dropout detection; shared streaming analysis; persisted SQLite scan results and cache; versioned quality scores; CSV export and Rich console reports.

**Important:** Quality scores and timestamps are diagnostic hints. Always listen to flagged passages before replacing or discarding files. Original MP3s are not modified.

**Requirements:** Python 3.12, FFmpeg/FFprobe and `uv` for source-based installation.

**Before publishing:** confirm tested CLI command, license, distribution metadata and real-world validation results.
