from __future__ import annotations

import os
from pathlib import Path


def load_env_file(
    env_path: str | os.PathLike[str] | None = None,
    *,
    override: bool = False,
) -> dict[str, str]:
    path = Path(env_path or ".env")
    if not path.exists() or not path.is_file():
        return {}

    loaded: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if line.startswith("export "):
            line = line[7:].strip()

        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue

        if value and value[0] in {"'", '"'} and value[-1] == value[0]:
            value = value[1:-1]

        if override or key not in os.environ:
            os.environ[key] = value
            loaded[key] = value

    return loaded
