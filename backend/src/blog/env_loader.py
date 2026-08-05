from __future__ import annotations

import os
import warnings
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
    try:
        content = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        warnings.warn(f"无法以 UTF-8 读取环境文件 {path}: {exc}", RuntimeWarning, stacklevel=2)
        return {}
    except OSError as exc:
        warnings.warn(f"无法读取环境文件 {path}: {exc}", RuntimeWarning, stacklevel=2)
        return {}

    for raw_line in content.splitlines():
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


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int, *, minimum: int | None = None) -> int:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        value = default
    else:
        try:
            value = int(str(raw).strip())
        except ValueError:
            warnings.warn(
                f"环境变量 {name}={raw!r} 不是有效整数，已回退到默认值 {default}。",
                RuntimeWarning,
                stacklevel=2,
            )
            value = default
    if minimum is not None:
        value = max(minimum, value)
    return value
