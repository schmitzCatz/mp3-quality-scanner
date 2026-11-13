# Changelog

All notable changes to this project are documented here. The project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) conventions and intends to use semantic versioning.

## [1.1.0]

## Added
- ID3 metadata persistence for title, album, artist, track number and disc number.
- ID3 metadata fields in CSV exports.
- SQLite schema v5 with automatic migration from previous versions.

## Improved
- Automatic recalculation of outdated quality scores.
- Preservation of cached scan results during quality model updates.
- Extended migration tests for schema v3 → v5 and v4 → v5.

## Fixed
- Corrected SQLite UPSERT handling for audio files and metadata.
- Fixed schema version detection for existing databases.

## Validation
- 85 automated tests passing.
- 
## [1.0.0]

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
