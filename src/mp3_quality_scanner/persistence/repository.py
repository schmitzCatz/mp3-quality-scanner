import csv
import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Self

from mp3_quality_scanner.domain.models import (
    AnalysisResult,
    AudioMetadata,
    Finding,
    ScanResult,
    Severity,
)
from mp3_quality_scanner.domain.quality import (
    QUALITY_MODEL_VERSION,
    assess_quality,
)
from mp3_quality_scanner.domain.tags import TrackTags

SCHEMA_VERSION = 5


@dataclass(frozen=True)
class QualitySummary:
    total: int
    critical: int
    review: int
    good: int
    unknown: int


@dataclass(frozen=True)
class QualityFile:
    path: str
    score: int | None
    label: str
    finding_count: int
    click_count: int
    click_rate: float | None


class ScanRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.connection = sqlite3.connect(self.database_path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")

        self._initialize()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: object,
        exc_value: object,
        traceback: object,
    ) -> None:
        self.close()

    def close(self) -> None:
        self.connection.close()

    @contextmanager
    def _transaction(self) -> Iterator[None]:
        with self.connection:
            yield

    def _initialize(self) -> None:
        version = int(self.connection.execute("PRAGMA user_version").fetchone()[0])

        if version > SCHEMA_VERSION:
            raise RuntimeError(f"Unsupported database schema version: {version}")

        # Detect databases without a recorded schema version.
        if version == 0:
            tables = {
                row["name"]
                for row in self.connection.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table'
                    """
                )
            }

            if "audio_file" not in tables:
                # Create a fresh database with the latest schema.
                self._create_schema()
                return

            # Existing database without a schema version:
            # determine its version from the available columns.
            columns = self._table_columns("audio_file")

            if {
                "quality_model_version",
                "title",
                "album",
                "artist",
                "track_number",
                "disc_number",
            }.issubset(columns):
                version = 5
            elif "quality_model_version" in columns:
                version = 4
            elif {
                "quality_score",
                "quality_label",
            }.issubset(columns):
                version = 3
            elif "scan_state" in columns:
                version = 2
            else:
                version = 1

        # Migrate schema v1 -> v2.
        if version < 2:
            self._migrate_to_v2()
            version = 2

        # Migrate schema v2 -> v3.
        if version < 3:
            self._migrate_to_v3()
            version = 3

        # Migrate schema v3 -> v4.
        if version < 4:
            self._migrate_to_v4()
            version = 4
        # Migrate schema v4 -> v5.
        if version < 5:
            self._migrate_to_v5()
            version = 5

        # Persist the current database schema version.
        with self._transaction():
            self.connection.execute(f"PRAGMA user_version = {version}")

        # Recalculate scores only for files whose quality
        # model version differs from the current version.
        #
        # This uses stored findings and metadata.
        # No MP3 decoding or FFmpeg invocation is required.
        self.recalculate_outdated_quality_scores()

    def _table_columns(
        self,
        table_name: str,
    ) -> set[str]:
        return {
            str(row["name"]) for row in self.connection.execute(f"PRAGMA table_info({table_name})")
        }

    def _create_schema(self) -> None:
        with self._transaction():
            self.connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS audio_file
                (
                    id
                    INTEGER
                    PRIMARY
                    KEY,
                    path
                    TEXT
                    NOT
                    NULL
                    UNIQUE,
                    size
                    INTEGER
                    NOT
                    NULL,
                    mtime_ns
                    INTEGER
                    NOT
                    NULL,
                    status
                    TEXT
                    NOT
                    NULL,
                    scanned_at
                    TEXT
                    NOT
                    NULL,
                    analyzer_fingerprint
                    TEXT
                    NOT
                    NULL,
                    scan_state
                    TEXT
                    NOT
                    NULL
                    DEFAULT
                    'completed',
                    quality_score
                    INTEGER,
                    quality_label
                    TEXT,
                    quality_model_version
                    INTEGER,
                    title
                    TEXT,
                    album
                    TEXT,
                    artist
                    TEXT,
                    track_number
                    INTEGER,
                    disc_number
                    INTEGER
                );

                CREATE TABLE IF NOT EXISTS analysis
                (
                    id
                    INTEGER
                    PRIMARY
                    KEY,
                    audio_file_id
                    INTEGER
                    NOT
                    NULL,
                    analyzer
                    TEXT
                    NOT
                    NULL,
                    codec
                    TEXT,
                    duration_seconds
                    REAL,
                    bitrate
                    INTEGER,
                    sample_rate
                    INTEGER,
                    channels
                    INTEGER,
                    FOREIGN
                    KEY
                (
                    audio_file_id
                )
                    REFERENCES audio_file
                (
                    id
                )
                    ON DELETE CASCADE
                    );

                CREATE TABLE IF NOT EXISTS finding
                (
                    id
                    INTEGER
                    PRIMARY
                    KEY,
                    analysis_id
                    INTEGER
                    NOT
                    NULL,
                    code
                    TEXT
                    NOT
                    NULL,
                    severity
                    TEXT
                    NOT
                    NULL,
                    message
                    TEXT
                    NOT
                    NULL,
                    position_seconds
                    REAL,
                    FOREIGN
                    KEY
                (
                    analysis_id
                )
                    REFERENCES analysis
                (
                    id
                )
                    ON DELETE CASCADE
                    );

                CREATE INDEX IF NOT EXISTS
                    idx_audio_file_status
                    ON audio_file(status);

                CREATE INDEX IF NOT EXISTS
                    idx_audio_file_quality
                    ON audio_file(quality_score);

                CREATE INDEX IF NOT EXISTS
                    idx_analysis_audio_file
                    ON analysis(audio_file_id);

                CREATE INDEX IF NOT EXISTS
                    idx_finding_analysis
                    ON finding(analysis_id);
                """
            )

            self.connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    def _migrate_to_v2(self) -> None:
        columns = self._table_columns("audio_file")

        with self._transaction():
            if "scan_state" not in columns:
                self.connection.execute(
                    """
                    ALTER TABLE audio_file
                        ADD COLUMN scan_state TEXT NOT NULL
                            DEFAULT 'completed'
                    """
                )

            self.connection.execute("PRAGMA user_version = 2")

    def _migrate_to_v3(self) -> None:
        columns = self._table_columns("audio_file")

        with self._transaction():
            if "quality_score" not in columns:
                self.connection.execute(
                    """
                    ALTER TABLE audio_file
                        ADD COLUMN quality_score INTEGER
                    """
                )

            if "quality_label" not in columns:
                self.connection.execute(
                    """
                    ALTER TABLE audio_file
                        ADD COLUMN quality_label TEXT
                    """
                )

            self.connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                    idx_audio_file_quality
                    ON audio_file(quality_score)
                """
            )

            self.connection.execute("PRAGMA user_version = 3")

    def _migrate_to_v4(self) -> None:
        columns = self._table_columns("audio_file")

        with self._transaction():
            if "quality_model_version" not in columns:
                self.connection.execute(
                    """
                    ALTER TABLE audio_file
                        ADD COLUMN quality_model_version INTEGER
                    """
                )

            self.connection.execute("PRAGMA user_version = 4")

    def _migrate_to_v5(self) -> None:
        columns = self._table_columns("audio_file")

        new_columns = {
            "title": "TEXT",
            "album": "TEXT",
            "artist": "TEXT",
            "track_number": "INTEGER",
            "disc_number": "INTEGER",
        }

        with self._transaction():
            for name, column_type in new_columns.items():
                if name not in columns:
                    self.connection.execute(
                        f"ALTER TABLE audio_file ADD COLUMN {name} {column_type}"
                    )

            self.connection.execute("PRAGMA user_version = 5")

    def _backfill_quality_scores(self) -> None:
        rows = self.connection.execute(
            """
            SELECT id, path, scan_state
            FROM audio_file
            """
        ).fetchall()

        with self._transaction():
            for row in rows:
                file_id = int(row["id"])

                if row["scan_state"] != "completed":
                    continue

                result = self._load_result(
                    file_id=file_id,
                    path=Path(str(row["path"])),
                )

                if not result.analyses:
                    continue

                assessment = assess_quality(result)

                self.connection.execute(
                    """
                    UPDATE audio_file
                    SET quality_score = ?,
                        quality_label = ?,
                        quality_model_version = ?
                    WHERE id = ?
                    """,
                    (
                        assessment.score,
                        assessment.label,
                        QUALITY_MODEL_VERSION,
                        file_id,
                    ),
                )

    def is_current(
        self,
        relative_path: str,
        size: int,
        mtime_ns: int,
        fingerprint: str,
    ) -> bool:
        row = self.connection.execute(
            """
            SELECT size, mtime_ns, analyzer_fingerprint, scan_state
            FROM audio_file
            WHERE path = ?
            """,
            (relative_path,),
        ).fetchone()

        if row is None:
            return False

        return bool(
            row["size"] == size
            and row["mtime_ns"] == mtime_ns
            and row["analyzer_fingerprint"] == fingerprint
            and row["scan_state"] == "completed"
        )

    def save(
        self,
        relative_path: str,
        size: int,
        mtime_ns: int,
        result: ScanResult,
        fingerprint: str,
        scan_state: str = "completed",
        tags: TrackTags | None = None,
    ) -> None:
        assessment = assess_quality(result) if scan_state == "completed" else None

        quality_score = assessment.score if assessment is not None else None

        quality_label = assessment.label if assessment is not None else None

        scanned_at = datetime.now(UTC).isoformat()

        tags = tags or TrackTags()

        with self._transaction():
            self.connection.execute(
                """
                    INSERT INTO audio_file (path,
                                            size,
                                            mtime_ns,
                                            status,
                                            scanned_at,
                                            analyzer_fingerprint,
                                            scan_state,
                                            quality_score,
                                            quality_label,
                                            quality_model_version,
                                            title,
                                            album,
                                            artist,
                                            track_number,
                                            disc_number)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(path) DO
                    UPDATE SET
                        size = excluded.size,
                        mtime_ns = excluded.mtime_ns,
                        status = excluded.status,
                        scanned_at = excluded.scanned_at,
                        analyzer_fingerprint = excluded.analyzer_fingerprint,
                        scan_state = excluded.scan_state,
                        quality_score = excluded.quality_score,
                        quality_label = excluded.quality_label,
                        quality_model_version = excluded.quality_model_version,
                        title = excluded.title,
                        album = excluded.album,
                        artist = excluded.artist,
                        track_number = excluded.track_number,
                        disc_number = excluded.disc_number
                    """,
                (
                    relative_path,
                    size,
                    mtime_ns,
                    result.status,
                    scanned_at,
                    fingerprint,
                    scan_state,
                    quality_score,
                    quality_label,
                    QUALITY_MODEL_VERSION if assessment is not None else None,
                    tags.title,
                    tags.album,
                    tags.artist,
                    tags.track_number,
                    tags.disc_number,
                ),
            )

            file_row = self.connection.execute(
                """
                SELECT id
                FROM audio_file
                WHERE path = ?
                """,
                (relative_path,),
            ).fetchone()

            if file_row is None:
                raise RuntimeError(f"Failed to save audio file: {relative_path}")

            file_id = int(file_row["id"])

            # Remove previous findings and analyses.
            self.connection.execute(
                """
                DELETE
                FROM finding
                WHERE analysis_id IN (SELECT id
                                      FROM analysis
                                      WHERE audio_file_id = ?)
                """,
                (file_id,),
            )

            self.connection.execute(
                """
                DELETE
                FROM analysis
                WHERE audio_file_id = ?
                """,
                (file_id,),
            )

            for analysis in result.analyses:
                self._save_analysis(
                    file_id,
                    analysis,
                )

    def _save_analysis(
        self,
        file_id: int,
        analysis: AnalysisResult,
    ) -> None:
        metadata = analysis.metadata

        cursor = self.connection.execute(
            """
            INSERT INTO analysis (audio_file_id,
                                  analyzer,
                                  codec,
                                  duration_seconds,
                                  bitrate,
                                  sample_rate,
                                  channels)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                file_id,
                analysis.analyzer,
                metadata.codec if metadata else None,
                (metadata.duration_seconds if metadata else None),
                metadata.bitrate if metadata else None,
                (metadata.sample_rate if metadata else None),
                metadata.channels if metadata else None,
            ),
        )

        analysis_id = cursor.lastrowid

        if analysis_id is None:
            raise RuntimeError("Failed to insert analysis")

        for finding in analysis.findings:
            self.connection.execute(
                """
                INSERT INTO finding (analysis_id,
                                     code,
                                     severity,
                                     message,
                                     position_seconds)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    analysis_id,
                    finding.code,
                    finding.severity.value,
                    finding.message,
                    finding.position_seconds,
                ),
            )

    def _load_result(
        self,
        file_id: int,
        path: Path,
    ) -> ScanResult:
        rows = self.connection.execute(
            """
            SELECT a.id,
                   a.analyzer,
                   a.codec,
                   a.duration_seconds,
                   a.bitrate,
                   a.sample_rate,
                   a.channels
            FROM analysis a
            WHERE a.audio_file_id = ?
            ORDER BY a.id
            """,
            (file_id,),
        ).fetchall()

        analyses: list[AnalysisResult] = []

        for row in rows:
            metadata = None

            if row["codec"] is not None:
                metadata = AudioMetadata(
                    codec=str(row["codec"]),
                    duration_seconds=row["duration_seconds"],
                    bitrate=row["bitrate"],
                    sample_rate=row["sample_rate"],
                    channels=row["channels"],
                )

            finding_rows = self.connection.execute(
                """
                SELECT code,
                       severity,
                       message,
                       position_seconds
                FROM finding
                WHERE analysis_id = ?
                ORDER BY id
                """,
                (row["id"],),
            ).fetchall()

            findings = [
                Finding(
                    code=str(finding["code"]),
                    severity=Severity(finding["severity"]),
                    message=str(finding["message"]),
                    position_seconds=(finding["position_seconds"]),
                )
                for finding in finding_rows
            ]

            analyses.append(
                AnalysisResult(
                    analyzer=str(row["analyzer"]),
                    metadata=metadata,
                    findings=findings,
                )
            )

        return ScanResult(
            path=path,
            analyses=analyses,
        )

    def export_csv(
        self,
        output_path: Path,
    ) -> None:
        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        rows = self.connection.execute(
            """
            SELECT af.id,
                   af.path,
                   af.title,
                   af.album,
                   af.artist,
                   af.track_number,
                   af.disc_number,
                   af.size,
                   af.mtime_ns,
                   af.status,
                   af.scanned_at,
                   af.scan_state,
                   af.quality_score,
                   af.quality_label,
                   COUNT(
                           CASE
                               WHEN f.code = 'POSSIBLE_CLICK'
                                   THEN 1
                               END
                   )           AS click_count,
                   COUNT(f.id) AS finding_count
            FROM audio_file af
                     LEFT JOIN analysis a
                               ON a.audio_file_id = af.id
                     LEFT JOIN finding f
                               ON f.analysis_id = a.id
            GROUP BY af.id
            ORDER BY af.quality_score IS NULL,
                     af.quality_score ASC,
                     af.path ASC
            """
        ).fetchall()

        fieldnames = [
            "path",
            "title",
            "album",
            "artist",
            "track_number",
            "disc_number",
            "size",
            "mtime_ns",
            "status",
            "scanned_at",
            "scan_state",
            "quality_score",
            "quality_label",
            "click_count",
            "finding_count",
            "findings",
        ]

        with output_path.open(
            "w",
            newline="",
            encoding="utf-8-sig",
        ) as file:
            writer = csv.DictWriter(
                file,
                fieldnames=fieldnames,
            )

            writer.writeheader()

            for row in rows:
                finding_rows = self.connection.execute(
                    """
                    SELECT f.code,
                           f.severity,
                           f.message,
                           f.position_seconds
                    FROM finding f
                             JOIN analysis a
                                  ON a.id = f.analysis_id
                    WHERE a.audio_file_id = ?
                    ORDER BY f.id
                    """,
                    (row["id"],),
                ).fetchall()

                findings = [
                    {
                        "code": finding["code"],
                        "severity": finding["severity"],
                        "message": finding["message"],
                        "position_seconds": (finding["position_seconds"]),
                    }
                    for finding in finding_rows
                ]

                writer.writerow(
                    {
                        "path": row["path"],
                        "title": row["title"],
                        "album": row["album"],
                        "artist": row["artist"],
                        "track_number": row["track_number"],
                        "disc_number": row["disc_number"],
                        "size": row["size"],
                        "mtime_ns": row["mtime_ns"],
                        "status": row["status"],
                        "scanned_at": row["scanned_at"],
                        "scan_state": row["scan_state"],
                        "quality_score": (row["quality_score"]),
                        "quality_label": (row["quality_label"]),
                        "click_count": (row["click_count"]),
                        "finding_count": (row["finding_count"]),
                        "findings": json.dumps(
                            findings,
                            ensure_ascii=False,
                        ),
                    }
                )

    def get_quality_summary(self) -> QualitySummary:
        row = self.connection.execute(
            """
            SELECT COUNT(*) AS total,
                   COUNT(CASE
                             WHEN quality_label = 'critical'
                                 THEN 1 END
                   )        AS critical,
                   COUNT(CASE
                             WHEN quality_label = 'review'
                                 THEN 1 END
                   )        AS review,
                   COUNT(CASE
                             WHEN quality_label = 'good'
                                 THEN 1 END
                   )        AS good,
                   COUNT(CASE
                             WHEN quality_label IS NULL
                                 OR quality_label = 'unknown'
                                 THEN 1 END
                   ) AS unknown
            FROM audio_file
            """
        ).fetchone()

        assert row is not None

        return QualitySummary(
            total=int(row["total"]),
            critical=int(row["critical"]),
            review=int(row["review"]),
            good=int(row["good"]),
            unknown=int(row["unknown"]),
        )

    def get_worst_files(
        self,
        limit: int = 20,
    ) -> list[QualityFile]:
        rows = self.connection.execute(
            """
            SELECT af.path,
                   af.quality_score,
                   af.quality_label,
                   COUNT(f.id)                     AS finding_count,
                   COUNT(
                           CASE
                               WHEN f.code = 'POSSIBLE_CLICK'
                                   THEN 1
                               END
                   )                               AS click_count,
                   (SELECT MAX(a2.duration_seconds)
                    FROM analysis a2
                    WHERE a2.audio_file_id = af.id
                      AND a2.duration_seconds > 0) AS duration_seconds
            FROM audio_file af
                     LEFT JOIN analysis a
                               ON a.audio_file_id = af.id
                     LEFT JOIN finding f
                               ON f.analysis_id = a.id
            WHERE af.quality_score IS NOT NULL
            GROUP BY af.id
            ORDER BY af.quality_score ASC,
                     click_count DESC,
                     af.path ASC LIMIT ?
            """,
            (limit,),
        ).fetchall()

        files: list[QualityFile] = []

        for row in rows:
            click_count = int(row["click_count"])

            duration = (
                float(row["duration_seconds"]) if row["duration_seconds"] is not None else None
            )

            click_rate = (
                click_count * 60.0 / duration if duration is not None and duration > 0 else None
            )

            files.append(
                QualityFile(
                    path=str(row["path"]),
                    score=int(row["quality_score"]),
                    label=str(row["quality_label"]),
                    finding_count=int(row["finding_count"]),
                    click_count=click_count,
                    click_rate=click_rate,
                )
            )

        return files

    def recalculate_quality_scores(self) -> int:
        rows = self.connection.execute(
            """
            SELECT id, path
            FROM audio_file
            WHERE scan_state = 'completed'
            """
        ).fetchall()

        updated = 0

        with self._transaction():
            for row in rows:
                result = self._load_result(
                    file_id=int(row["id"]),
                    path=Path(str(row["path"])),
                )

                if not result.analyses:
                    continue

                assessment = assess_quality(result)

                self.connection.execute(
                    """
                    UPDATE audio_file
                    SET quality_score = ?,
                        quality_label = ?,
                        quality_model_version = ?
                    WHERE id = ?
                    """,
                    (
                        assessment.score,
                        assessment.label,
                        QUALITY_MODEL_VERSION,
                        row["id"],
                    ),
                )

                updated += 1

        return updated

    def recalculate_outdated_quality_scores(self) -> int:
        """Recalculate scores when the quality model changes."""

        rows = self.connection.execute(
            """
            SELECT id, path
            FROM audio_file
            WHERE scan_state = 'completed'
              AND (
                quality_model_version IS NULL
                    OR quality_model_version != ?
                )
            """,
            (QUALITY_MODEL_VERSION,),
        ).fetchall()

        updated = 0

        with self._transaction():
            for row in rows:
                file_id = int(row["id"])

                result = self._load_result(
                    file_id=file_id,
                    path=Path(str(row["path"])),
                )

                if not result.analyses:
                    # Do not mark incomplete records as current.
                    continue

                assessment = assess_quality(result)

                self.connection.execute(
                    """
                    UPDATE audio_file
                    SET quality_score         = ?,
                        quality_label         = ?,
                        quality_model_version = ?
                    WHERE id = ?
                    """,
                    (
                        assessment.score,
                        assessment.label,
                        QUALITY_MODEL_VERSION,
                        file_id,
                    ),
                )

                updated += 1

        return updated
