# MP3 Quality Scanner — v1.1.0

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