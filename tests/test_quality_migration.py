from pathlib import Path

from mp3_quality_scanner.domain.models import (
    AnalysisResult,
    AudioMetadata,
    Finding,
    ScanResult,
    Severity,
)
from mp3_quality_scanner.domain.quality import QUALITY_MODEL_VERSION
from mp3_quality_scanner.persistence.repository import (
    SCHEMA_VERSION,
    ScanRepository,
)


def make_result() -> ScanResult:
    return ScanResult(
        path=Path("track.mp3"),
        analyses=[
            AnalysisResult(
                analyzer="integrity",
                metadata=AudioMetadata(
                    codec="mp3",
                    duration_seconds=300.0,
                    bitrate=320000,
                    sample_rate=44100,
                    channels=2,
                ),
            ),
            AnalysisResult(
                analyzer="click",
                findings=[
                    Finding(
                        code="POSSIBLE_CLICK",
                        severity=Severity.WARNING,
                        message="Test click",
                    )
                ],
            ),
        ],
    )


def test_new_database_uses_current_schema(
    tmp_path: Path,
) -> None:
    with ScanRepository(tmp_path / "test.db") as repository:
        version = repository.connection.execute("PRAGMA user_version").fetchone()[0]

        assert version == SCHEMA_VERSION


def test_new_scan_stores_model_version(
    tmp_path: Path,
) -> None:
    with ScanRepository(tmp_path / "test.db") as repository:
        repository.save(
            "track.mp3",
            100,
            1,
            make_result(),
            "fingerprint",
        )

        row = repository.connection.execute(
            """
            SELECT quality_score, quality_model_version
            FROM audio_file
            WHERE path = ?
            """,
            ("track.mp3",),
        ).fetchone()

        assert row is not None
        assert row["quality_score"] == 97
        assert row["quality_model_version"] == QUALITY_MODEL_VERSION


def test_outdated_score_is_recalculated(
    tmp_path: Path,
) -> None:
    database = tmp_path / "test.db"

    with ScanRepository(database) as repository:
        repository.save(
            "track.mp3",
            100,
            1,
            make_result(),
            "fingerprint",
        )

        # Simulate a score produced by an older model.
        with repository.connection:
            repository.connection.execute(
                """
                UPDATE audio_file
                SET quality_score = 92,
                    quality_model_version = 1
                WHERE path = ?
                """,
                ("track.mp3",),
            )

    # Reopening triggers automatic recalculation.
    with ScanRepository(database) as repository:
        row = repository.connection.execute(
            """
            SELECT quality_score, quality_model_version
            FROM audio_file
            WHERE path = ?
            """,
            ("track.mp3",),
        ).fetchone()

        assert row is not None
        assert row["quality_score"] == 97
        assert row["quality_model_version"] == QUALITY_MODEL_VERSION

        # A second recalculation must do no work.
        assert repository.recalculate_outdated_quality_scores() == 0


def test_recalculation_preserves_scan_cache(
    tmp_path: Path,
) -> None:
    database = tmp_path / "test.db"

    with ScanRepository(database) as repository:
        repository.save(
            "track.mp3",
            100,
            1,
            make_result(),
            "fingerprint",
        )

        with repository.connection:
            repository.connection.execute(
                """
                UPDATE audio_file
                SET quality_model_version = 1
                WHERE path = ?
                """,
                ("track.mp3",),
            )

    with ScanRepository(database) as repository:
        assert repository.is_current(
            "track.mp3",
            size=100,
            mtime_ns=1,
            fingerprint="fingerprint",
        )


def test_schema_v3_migrates_to_v5(
    tmp_path: Path,
) -> None:
    database = tmp_path / "test.db"

    # Create a database with the current schema.
    with ScanRepository(database) as repository:
        repository.save(
            "track.mp3",
            100,
            1,
            make_result(),
            "fingerprint",
        )

        connection = repository.connection

        # Disable foreign keys before starting a transaction.
        connection.execute("PRAGMA foreign_keys = OFF")

        try:
            with connection:
                # Simulate an outdated quality score.
                connection.execute(
                    """
                    UPDATE audio_file
                    SET quality_score = 92
                    WHERE path = ?
                    """,
                    ("track.mp3",),
                )

                # Rebuild the table using the historical v3 schema.
                # Preserve the original table name and record IDs.
                connection.execute(
                    """
                    CREATE TABLE audio_file_v3 AS
                    SELECT
                        id,
                        path,
                        size,
                        mtime_ns,
                        status,
                        scanned_at,
                        analyzer_fingerprint,
                        scan_state,
                        quality_score,
                        quality_label
                    FROM audio_file
                    """
                )

                connection.execute("DROP TABLE audio_file")

                connection.execute(
                    """
                    ALTER TABLE audio_file_v3
                    RENAME TO audio_file
                    """
                )

                connection.execute("PRAGMA user_version = 3")
        finally:
            connection.execute("PRAGMA foreign_keys = ON")

    # Opening the database triggers v3 -> v4 -> v5 migration.
    with ScanRepository(database) as repository:
        columns = repository._table_columns("audio_file")

        assert {
            "quality_model_version",
            "title",
            "album",
            "artist",
            "track_number",
            "disc_number",
        }.issubset(columns)

        version = repository.connection.execute("PRAGMA user_version").fetchone()[0]

        assert version == SCHEMA_VERSION

        row = repository.connection.execute(
            """
            SELECT
                id,
                quality_score,
                quality_model_version
            FROM audio_file
            WHERE path = ?
            """,
            ("track.mp3",),
        ).fetchone()

        assert row is not None

        # The migration must recalculate the outdated score.
        assert row["quality_score"] == 97
        assert row["quality_model_version"] == QUALITY_MODEL_VERSION

        # Previously stored analyses and findings must survive.
        result = repository._load_result(
            file_id=int(row["id"]),
            path=Path("track.mp3"),
        )

        assert len(result.analyses) == 2
        assert len(result.analyses[1].findings) == 1

        # Recalculation must not invalidate the scan cache.
        assert repository.is_current(
            "track.mp3",
            size=100,
            mtime_ns=1,
            fingerprint="fingerprint",
        )


def test_schema_v4_migrates_to_v5(
    tmp_path: Path,
) -> None:
    database = tmp_path / "test.db"

    with ScanRepository(database) as repository:
        repository.save(
            "track.mp3",
            100,
            1,
            make_result(),
            "fingerprint",
        )

        # Simulate schema v4 by removing ID3 columns.
        with repository.connection:
            repository.connection.execute(
                """
                CREATE TABLE audio_file_v4 AS
                SELECT
                    id,
                    path,
                    size,
                    mtime_ns,
                    status,
                    scanned_at,
                    analyzer_fingerprint,
                    scan_state,
                    quality_score,
                    quality_label,
                    quality_model_version
                FROM audio_file
                """
            )

            repository.connection.execute("DROP TABLE audio_file")

            repository.connection.execute(
                """
                ALTER TABLE audio_file_v4
                RENAME TO audio_file
                """
            )

            repository.connection.execute("PRAGMA user_version = 4")

    with ScanRepository(database) as repository:
        columns = repository._table_columns("audio_file")

        assert {
            "title",
            "album",
            "artist",
            "track_number",
            "disc_number",
        }.issubset(columns)

        version = repository.connection.execute("PRAGMA user_version").fetchone()[0]

        assert version == SCHEMA_VERSION

        # Existing quality scores must remain intact.
        row = repository.connection.execute(
            """
            SELECT
                quality_score,
                quality_model_version
            FROM audio_file
            WHERE path = ?
            """,
            ("track.mp3",),
        ).fetchone()

        assert row is not None
        assert row["quality_score"] == 97
        assert row["quality_model_version"] == QUALITY_MODEL_VERSION
