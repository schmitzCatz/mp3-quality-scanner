# Release procedure

## Before tagging

- [ ] Confirm current `pyproject.toml` metadata: name, version `1.0.0`, description, Python requirement, authors and project URLs.
- [ ] Confirm actual CLI entry point and invocation; replace README placeholder with a tested example.
- [ ] Choose and include a license, or explicitly decide on a private distribution.
- [ ] Verify `ffmpeg` and `ffprobe` availability and document supported platforms.
- [ ] Confirm quality model version and schema migration tests.
- [ ] Confirm Dropout Analyzer version/fingerprint changes are committed.
- [ ] Review false positives using a small, real-world MP3 corpus; preserve originals.
- [ ] Run formatting, linting, type checks and full tests.
- [ ] Build distributions and inspect wheel/sdist contents.
- [ ] Update CHANGELOG date and release notes.
- [ ] Ensure working tree is clean.

## Local checks (PowerShell)

```powershell
./scripts/verify-release.ps1
```

Inspect artifacts under `dist/` and ensure no local music, databases, or other sensitive data are packaged.

## Tagging (after checks pass)

```powershell
git status --short
git add README.md CHANGELOG.md RELEASING.md RELEASE_NOTES.md .github/workflows/release.yml scripts/verify-release.ps1
git commit -m "docs: prepare v1.0.0 release"
git tag -a v1.0.0 -m "MP3 Quality Scanner 1.0.0"
git push origin main
git push origin v1.0.0
```

Adjust `main` if the repository uses another default branch. Never create a tag before the metadata and docs match the release version.

## GitHub release

The included workflow runs checks and builds Python distributions for `v*` tags, then attaches artifacts to a GitHub Release. It **does not publish to PyPI**. Enable the workflow only after reviewing the project configuration and GitHub permissions.

## Rollback

If a release is faulty, publish a corrective patch release (e.g. `v1.0.1`) rather than silently moving an already published tag.
