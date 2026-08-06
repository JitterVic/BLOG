"""站点资料服务：资料读取、公开站点载荷与表单更新校验。"""

from __future__ import annotations

import re
from typing import Any

from ..validation import validate_text_length


class ProfileService:
    def __init__(self, profile_repo, posts_repo):
        self.profile_repo = profile_repo
        self.posts_repo = posts_repo

    def get_site_profile(self) -> dict[str, Any]:
        return self.profile_repo.get()

    def get_site_payload(self) -> dict[str, Any]:
        profile = self.get_site_profile()
        payload = {
            field: profile.get(field)
            for field in ("name", "headline", "summary", "social_links", "about_intro")
        }
        payload["tags"] = sorted(self.posts_repo.published_tags())
        return payload

    def update_site_profile(self, form_data: dict[str, Any]) -> None:
        current = self.get_site_profile()

        values = {
            field: validate_text_length(field, form_data.get(field, ""))
            for field in (
                "name", "headline", "summary", "email",
                "github_label", "github_url", "about_intro",
            )
        }
        name = values["name"] or current.get("name", "")
        if not name:
            raise ValueError("站点名称不能为空。")
        email = values["email"]
        if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            raise ValueError("Email 格式无效。")
        github_label = values["github_label"]
        github_url = values["github_url"]
        if github_url and not re.match(r"^https?://", github_url, re.IGNORECASE):
            raise ValueError("GitHub 链接必须使用 http:// 或 https://。")

        social_links = []
        if email:
            social_links.append({"label": "邮箱", "value": email, "url": f"mailto:{email}", "icon": "mail"})
        if github_label or github_url:
            social_links.append({"label": "GitHub 仓库", "value": github_label or github_url, "url": github_url, "icon": "github"})

        about_intro = [line.strip() for line in values["about_intro"].splitlines() if line.strip()]

        self.profile_repo.update(
            name=name,
            headline=values["headline"],
            summary=values["summary"],
            email=email,
            social_links=social_links,
            about_intro=about_intro,
        )
