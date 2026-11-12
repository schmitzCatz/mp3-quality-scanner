# MP3 Quality Scanner

A Python 3.12 tool for identifying potentially audible defects in MP3 collections. It scans recursively, persists results in SQLite, and supports reviewing suspicious files without modifying the originals.

> **Release candidate documentation for v1.0.0.** Verify the actual CLI entry point and options in your local `pyproject.toml` / CLI implementation before publishing. No command-line flags are assumed here.

## What it checks

| Analyzer | Purpose | Limitations |
| --- | --- | --- |
| Integrity | Uses FFprobe/FFmpeg to inspect metadata and decode errors | Successful decoding does not imply perceptually perfect audio |
| Clipping | Flags high clipping ratios and sustained clipping | Mastered/loud music can legitimately approach full scale |
| Click | Detects short, impulse-like anomalies | Percussive music can produce false positives |
| Dropout | Detects short near-silent intervals surrounded by stronger signal | Musical rests and gating can resemble dropouts; noisy dropouts may be missed |

The streaming analyzers share a PCM decoding pass. Integrity checking may perform an additional decode.

## Requirements

- Python 3.12
- [`uv`](https://docs.astral.sh/uv/)
- `ffmpeg` and `ffprobe` available on `PATH`
- Read access to your music collection and write access to the output directory

Check prerequisites:

```powershell
python --version
uv --version
ffmpeg -version
ffprobe -version
```

## Installation from source

```powershell
git clone <YOUR_REPOSITORY_URL>
cd mp3-quality-scanner
uv sync
uv run pytest
```

**Running a scan:** consult the entry point declared in `[project.scripts]` of `pyproject.toml` or the repository's CLI module. Confirm the actual command and flags before replacing this note with a copy/paste example.

## Configuration

The project uses Pydantic Settings with the `MP3QS_` environment-variable prefix. Known settings:

| Environment variable | Purpose | Default |
| --- | --- | --- |
| `MP3QS_MUSIC_DIR` | Root of MP3 collection | `/music` |
| `MP3QS_OUTPUT_DIR` | Directory for scan outputs | `/data` |
| `MP3QS_WORKERS` | Concurrent scan workers | `2` |

PowerShell example:

```powershell
$env:MP3QS_MUSIC_DIR = 'D:\Music'
$env:MP3QS_OUTPUT_DIR = 'D:\Music-Scan'
$env:MP3QS_WORKERS = '2'
```

Do not assume these variables create directories automatically; ensure the configured output directory is writable.

## Results

- **Rich console report:** summary by quality label and suspicious files.
- **SQLite database:** persisted file analyses, findings, metadata and quality assessments.
- **CSV export:** machine-readable results for sorting and filtering.
- **Scan cache:** unchanged files with matching analyzer fingerprints can be skipped.

### Quality labels

| Score | Label | Interpretation |
| --- | --- | --- |
| 80–100 | `good` | No strong indicators under the current heuristic |
| 50–79 | `review` | Review the reported timestamps by listening |
| 0–49 | `critical` | Prioritize manual review |
| Not available | `unknown` | Reliable scoring was not possible, for example due to decoding or analysis errors |

The score is **heuristic**, not a measurement of bitrate authenticity, lossless provenance, or guaranteed audibility. Click penalties depend on the detected click rate; clipping and dropout findings also affect the score. Thresholds and weights may evolve with a versioned scoring model.

### Recommended review workflow

1. Scan a small, representative sample of the library.
2. Sort by score and inspect `critical` files first.
3. Listen at the timestamps reported for clicks and dropouts.
4. Compare against another copy or source if available.
5. Keep the original files; make replacement decisions manually.

## Privacy and data safety

The scanner operates on local files. Its analysis is read-only with respect to the MP3 source files. Scan metadata and file paths are stored in the configured output database and may appear in CSV exports. Treat those outputs as potentially sensitive if paths contain personal information.

## Development

```powershell
uv sync
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest
uv build
```

See [RELEASING.md](RELEASING.md) for release preparation and verification.

## Known limitations

- Synthetic test success does not establish a low false-positive rate across real music genres.
- MP3 decoder output can mask or alter some encoded defects.
- A track can sound bad despite receiving a high score.
- No automatic restoration, transcoding or file replacement is performed.

## License

**Not selected yet.** Add a `LICENSE` file and update this section before a public release. Do not publish under an assumed license.
