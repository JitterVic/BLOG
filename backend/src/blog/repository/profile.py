"""站点资料仓储：site_profile 表读写。"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from .posts import row_to_dict


class ProfileRepository:
    def __init__(self, db):
        self.db = db

    def get(self) -> dict[str, Any]:
        with self.db.connect() as connection:
            row = connection.execute("SELECT * FROM site_profile WHERE id = 1").fetchone()
        return row_to_dict(row) or {}

    def update(
        self,
        *,
        name: str,
        headline: str,
        summary: str,
        email: str,
        social_links: list[dict[str, Any]],
        about_intro: list[str],
    ) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        with self.db.connect() as connection:
            connection.execute(
                """
                UPDATE site_profile
                SET name = ?, headline = ?, summary = ?,
                    email = ?, social_links = ?, about_intro = ?,
                    updated_at = ?
                WHERE id = 1
                """,
                (
                    name, headline, summary,
                    email, json.dumps(social_links, ensure_ascii=False),
                    json.dumps(about_intro, ensure_ascii=False),
                    now,
                ),
            )
            connection.commit()
