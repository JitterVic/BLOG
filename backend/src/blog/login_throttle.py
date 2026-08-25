"""登录失败计数存储：跨 gunicorn worker 共享、可重启存活。

进程内 dict 有两个缺陷：多 worker 各持一份桶会把有效额度乘以 worker 数，
而 gunicorn 的 ``--max-requests`` 回收 worker 时会把桶清零，等于白送攻击者
一次重置。这里把计数放进已有的 SQLite，并保留 dict 风格的接口，方便测试和
既有代码继续按映射方式读取。

任何 SQLite 故障都会退回到进程内 dict，确保登录路径不会因为限流存储不可用
而整体不可用。
"""

from __future__ import annotations

import sqlite3
import time
from typing import Iterator


class LoginFailureStore:
    """Mapping-like view over the ``login_failures`` table.

    Keys are client identifiers; values are lists of failure timestamps
    (wall-clock seconds, so they are comparable across processes).
    """

    def __init__(self, db, *, window_seconds: int, max_keys: int):
        self.db = db
        self.window_seconds = max(1, int(window_seconds))
        self.max_keys = max(1, int(max_keys))
        # Fallback used only when SQLite is unavailable.
        self._memory: dict[str, list[float]] = {}
        self._degraded = False

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    def _cutoff(self, now: float | None = None) -> float:
        return (now if now is not None else time.time()) - self.window_seconds

    def _connect(self):
        return self.db.connect()

    def _fallback(self, exc: Exception) -> None:
        self._degraded = True

    # ------------------------------------------------------------------
    # 写入
    # ------------------------------------------------------------------

    def record_failure(self, key: str, *, now: float | None = None) -> None:
        stamp = now if now is not None else time.time()
        try:
            with self._connect() as connection:
                connection.execute(
                    "INSERT INTO login_failures (client_key, failed_at) VALUES (?, ?)",
                    (str(key), float(stamp)),
                )
                connection.execute(
                    "DELETE FROM login_failures WHERE failed_at <= ?", (self._cutoff(stamp),)
                )
                # Bound the table: keep only the most recently active buckets.
                connection.execute(
                    """
                    DELETE FROM login_failures
                    WHERE client_key NOT IN (
                        SELECT client_key FROM login_failures
                        GROUP BY client_key
                        ORDER BY MAX(failed_at) DESC
                        LIMIT ?
                    )
                    """,
                    (self.max_keys,),
                )
                connection.commit()
        except sqlite3.Error as exc:
            self._fallback(exc)
            self._memory.setdefault(str(key), []).append(float(stamp))

    def attempts(self, key: str, *, now: float | None = None) -> list[float]:
        """Failure timestamps for *key* inside the current window, oldest first."""
        cutoff = self._cutoff(now)
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """
                    SELECT failed_at FROM login_failures
                    WHERE client_key = ? AND failed_at > ?
                    ORDER BY failed_at ASC
                    """,
                    (str(key), cutoff),
                ).fetchall()
            return [float(row[0]) for row in rows]
        except sqlite3.Error as exc:
            self._fallback(exc)
            return [s for s in self._memory.get(str(key), []) if s > cutoff]

    def prune(self, *, now: float | None = None) -> None:
        try:
            with self._connect() as connection:
                connection.execute(
                    "DELETE FROM login_failures WHERE failed_at <= ?", (self._cutoff(now),)
                )
                connection.commit()
        except sqlite3.Error as exc:
            self._fallback(exc)
            cutoff = self._cutoff(now)
            for key in list(self._memory):
                kept = [s for s in self._memory[key] if s > cutoff]
                if kept:
                    self._memory[key] = kept
                else:
                    self._memory.pop(key, None)

    # ------------------------------------------------------------------
    # dict 兼容接口（既有代码与测试沿用映射语义）
    # ------------------------------------------------------------------

    def _active_map(self, *, now: float | None = None) -> dict[str, list[float]]:
        cutoff = self._cutoff(now)
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """
                    SELECT client_key, failed_at FROM login_failures
                    WHERE failed_at > ?
                    ORDER BY failed_at ASC
                    """,
                    (cutoff,),
                ).fetchall()
            grouped: dict[str, list[float]] = {}
            for row in rows:
                grouped.setdefault(str(row[0]), []).append(float(row[1]))
            return grouped
        except sqlite3.Error as exc:
            self._fallback(exc)
            return {
                key: [s for s in stamps if s > cutoff]
                for key, stamps in self._memory.items()
                if any(s > cutoff for s in stamps)
            }

    def get(self, key: str, default=None):
        stamps = self.attempts(key)
        return stamps if stamps else default

    def pop(self, key: str, default=None):
        stamps = self.attempts(key)
        try:
            with self._connect() as connection:
                connection.execute("DELETE FROM login_failures WHERE client_key = ?", (str(key),))
                connection.commit()
        except sqlite3.Error as exc:
            self._fallback(exc)
        self._memory.pop(str(key), None)
        return stamps if stamps else default

    def clear(self) -> None:
        try:
            with self._connect() as connection:
                connection.execute("DELETE FROM login_failures")
                connection.commit()
        except sqlite3.Error as exc:
            self._fallback(exc)
        self._memory.clear()

    def items(self):
        return self._active_map().items()

    def keys(self):
        return self._active_map().keys()

    def values(self):
        return self._active_map().values()

    def __getitem__(self, key: str) -> list[float]:
        stamps = self.attempts(key)
        if not stamps:
            raise KeyError(key)
        return stamps

    def __setitem__(self, key: str, stamps) -> None:
        """Replace a bucket wholesale (used when trimming to the window)."""
        values = [float(s) for s in (stamps or [])]
        try:
            with self._connect() as connection:
                connection.execute("DELETE FROM login_failures WHERE client_key = ?", (str(key),))
                connection.executemany(
                    "INSERT INTO login_failures (client_key, failed_at) VALUES (?, ?)",
                    [(str(key), value) for value in values],
                )
                connection.commit()
            return
        except sqlite3.Error as exc:
            self._fallback(exc)
        if values:
            self._memory[str(key)] = values
        else:
            self._memory.pop(str(key), None)

    def __contains__(self, key: object) -> bool:
        return bool(self.attempts(str(key)))

    def __iter__(self) -> Iterator[str]:
        return iter(self._active_map())

    def __len__(self) -> int:
        return len(self._active_map())

    def __repr__(self) -> str:
        state = "degraded-memory" if self._degraded else "sqlite"
        return f"<LoginFailureStore {state} buckets={len(self)}>"
