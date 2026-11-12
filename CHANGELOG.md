# Changelog

All notable changes to this project are documented here. The project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) conventions and intends to use semantic versioning.

## [1.0.0] - Unreleased

### Added
- Recursive MP3 discovery and file metadata inspection.
- FFmpeg/FFprobe integrity checks.
- Shared PCM streaming pipeline with clipping, click and dropout analyzers.
- Heuristic, duration-aware quality scoring with `good`, `review`, `critical` and `unknown` labels.
- SQLite persistence, scan caching, analyzer fingerprints and schema migrations.
- Quality-model versioning and automatic score recalculation from stored findings.
- Rich terminal summaries and CSV export.
- Automated tests including synthetic audio signals and chunk-boundary cases.

### Notes
- Findings are indicators for manual listening, not conclusive proof of audible damage.
- Validate release on a representative real-world collection before changing this heading to a release date.
