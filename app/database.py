import sqlite3
import uuid
from datetime import datetime, timezone

DB_PATH = "ingestion.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audio_files (
            id          TEXT PRIMARY KEY,
            filename    TEXT NOT NULL,
            sample_rate INTEGER NOT NULL,
            num_channels INTEGER NOT NULL,
            num_samples  INTEGER NOT NULL,
            audio_blob  BLOB NOT NULL,
            created_at  TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def get_audio(audio_id: str) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT id, filename, sample_rate, num_channels, num_samples, audio_blob FROM audio_files WHERE id = ?",
        (audio_id,),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)


def insert_audio(
    filename: str,
    sample_rate: int,
    num_channels: int,
    num_samples: int,
    audio_blob: bytes,
) -> str:
    audio_id = str(uuid.uuid4())
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO audio_files
            (id, filename, sample_rate, num_channels, num_samples, audio_blob, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            audio_id,
            filename,
            sample_rate,
            num_channels,
            num_samples,
            audio_blob,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    conn.close()
    return audio_id
