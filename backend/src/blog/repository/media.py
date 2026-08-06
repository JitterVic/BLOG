"""媒体元数据仓储：media_metadata 表（上传原始文件名记录）。"""

from __future__ import annotations

from datetime import datetime


class MediaRepository:
    def __init__(self, db):
        self.db = db

    def metadata_map(self) -> dict[str, str]:
        with self.db.connect() as connection:
            rows = connection.execute(
                "SELECT path, original_filename FROM media_metadata"
            ).fetchall()
        return {str(row["path"]): str(row["original_filename"] or "") for row in rows}

    def upsert_metadata(self, relative_path: str, original_filename: str) -> None:
        now = datetime.now().isoformat(timespec="microseconds")
        with self.db.connect() as connection:
            connection.execute(
                """
                INSERT INTO media_metadata (path, original_filename, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(path) DO UPDATE SET original_filename = excluded.original_filename
                """,
                (relative_path, original_filename, now),
            )
            connection.commit()
