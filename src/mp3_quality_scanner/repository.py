import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from mp3_quality_scanner.models import (
    AnalysisResult,
    ScanResult,
)


class ScanRepository:
    def __init__(self, database: Path) -> None:
        database.parent.mkdir(parents=True, exist_ok=True)

        self.connection = sqlite3.connect(database)
        self.connection.execute("PRAGMA foreign_keys = ON")
        self._initialize()

    def _initialize(self) -> None:
        with self.connection:
            self.connection.executescript("""
                CREATE TABLE IF NOT EXISTS audio_file (
                    id INTEGER PRIMARY KEY,
                    path TEXT NOT NULL UNIQUE,
                    size INTEGER NOT NULL,
                    mtime_ns INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    scanned_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS analysis (
                    id INTEGER PRIMARY KEY,
                    audio_file_id INTEGER NOT NULL,
                    analyzer TEXT NOT NULL,
                    codec TEXT,
                    duration_seconds REAL,
                    bitrate INTEGER,
                    sample_rate INTEGER,
                    channels INTEGER,
                    FOREIGN KEY (audio_file_id)
                        REFERENCES audio_file(id)
                        ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS finding (
                    id INTEGER PRIMARY KEY,
                    analysis_id INTEGER NOT NULL,
                    code TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    message TEXT NOT NULL,
                    position_seconds REAL,
                    FOREIGN KEY (analysis_id)
                        REFERENCES analysis(id)
                        ON DELETE CASCADE
                );
            """)

            self.connection.execute("PRAGMA user_version = 1")

    def is_current(
        self,
        path: str,
        size: int,
        mtime_ns: int,
    ) -> bool:
        row = self.connection.execute(
            """
            SELECT 1 FROM audio_file
            WHERE path = ?
              AND size = ?
              AND mtime_ns = ?
            """,
            (path, size, mtime_ns),
        ).fetchone()

        return row is not None

    def save(
        self,
        relative_path: str,
        size: int,
        mtime_ns: int,
        result: ScanResult,
    ) -> None:
        scanned_at = datetime.now(UTC).isoformat()

        with self.connection:
            self.connection.execute(
                """
                INSERT INTO audio_file (
                    path, size, mtime_ns, status, scanned_at
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(path) DO UPDATE SET
                    size = excluded.size,
                    mtime_ns = excluded.mtime_ns,
                    status = excluded.status,
                    scanned_at = excluded.scanned_at
                """,
                (
                    relative_path,
                    size,
                    mtime_ns,
                    result.status,
                    scanned_at,
                ),
            )

            row = self.connection.execute(
                "SELECT id FROM audio_file WHERE path = ?",
                (relative_path,),
            ).fetchone()

            if row is None:
                raise RuntimeError("Failed to retrieve audio file ID")

            file_id = int(row[0])

            self.connection.execute(
                "DELETE FROM analysis WHERE audio_file_id = ?",
                (file_id,),
            )

            for analysis in result.analyses:
                self._save_analysis(file_id, analysis)

    def _save_analysis(
        self,
        file_id: int,
        analysis: AnalysisResult,
    ) -> None:
        metadata = analysis.metadata

        cursor = self.connection.execute(
            """
            INSERT INTO analysis (
                audio_file_id,
                analyzer,
                codec,
                duration_seconds,
                bitrate,
                sample_rate,
                channels
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                file_id,
                analysis.analyzer,
                metadata.codec if metadata else None,
                metadata.duration_seconds if metadata else None,
                metadata.bitrate if metadata else None,
                metadata.sample_rate if metadata else None,
                metadata.channels if metadata else None,
            ),
        )

        analysis_id = cursor.lastrowid

        for finding in analysis.findings:
            self.connection.execute(
                """
                INSERT INTO finding (
                    analysis_id,
                    code,
                    severity,
                    message,
                    position_seconds
                )
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

    def export_csv(self, output: Path) -> None:
        import csv

        output.parent.mkdir(parents=True, exist_ok=True)

        rows = self.connection.execute("""
            SELECT
                af.path,
                af.status,
                a.analyzer,
                f.code,
                f.severity,
                f.message,
                f.position_seconds
            FROM audio_file af
            LEFT JOIN analysis a
                ON a.audio_file_id = af.id
            LEFT JOIN finding f
                ON f.analysis_id = a.id
            ORDER BY af.path, a.analyzer, f.id
        """)

        with output.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(
                [
                    "file",
                    "status",
                    "analyzer",
                    "code",
                    "severity",
                    "message",
                    "position_seconds",
                ]
            )
            writer.writerows(rows)

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "ScanRepository":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()
