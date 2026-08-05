#!/usr/bin/env bash
# deploy/backup.sh — WAL 安全的数据库与媒体备份
# 环境变量：APP_DIR / BACKUP_DIR / KEEP / PYTHON_BIN
set -Eeuo pipefail

APP_DIR="${APP_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
BACKUP_DIR="${BACKUP_DIR:-${APP_DIR}/storage-backups}"
KEEP="${KEEP:-7}"
PYTHON_BIN="${PYTHON_BIN:-${APP_DIR}/backend/.venv/bin/python}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"

log() { printf '\033[1;36m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33mWARN: %s\033[0m\n' "$*"; }
fail() { printf '\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

command -v "$PYTHON_BIN" >/dev/null 2>&1 || fail "找不到 Python：$PYTHON_BIN"

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# ---------------------------------------------------------------------------
# 1. WAL 安全的 SQLite 快照（stdlib sqlite3 Connection.backup，零新依赖）
# ---------------------------------------------------------------------------
log "创建数据库一致性快照"
"$PYTHON_BIN" - "$WORK/blog.db" <<'PY'
import os, sqlite3, sys
from pathlib import Path

root = Path(os.environ["APP_DIR"]).resolve()
from blog.env_loader import load_env_file
load_env_file(root / ".env")

raw = Path(os.getenv("BLOG_DATABASE_PATH") or (root / "storage" / "blog.db"))
db = raw if raw.is_absolute() else root / raw  # 与 store.py 保持一致

dst_path = sys.argv[1]
src = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
dst = sqlite3.connect(dst_path)
with dst:
    src.backup(dst)  # 在线备份 API，WAL 安全
src.close()

check = dst.execute("PRAGMA integrity_check").fetchone()[0]
dst.close()
if check != "ok":
    raise SystemExit(f"备份完整性校验失败：{check}")

print(f"数据库快照完成：{db}")
PY

# ---------------------------------------------------------------------------
# 2. 白名单拷贝媒体（不含 blog.db-wal/-shm，不含 storage/backup-* 历史目录）
# ---------------------------------------------------------------------------
log "拷贝媒体文件"
for d in avatars media; do
  if [[ -d "${APP_DIR}/storage/$d" ]]; then
    cp -a "${APP_DIR}/storage/$d" "$WORK/"
  fi
done

# ---------------------------------------------------------------------------
# 3. 清单
# ---------------------------------------------------------------------------
db_size="$(wc -c < "$WORK/blog.db" | tr -d ' ')"
git_rev="$(cd "$APP_DIR" && git rev-parse --short HEAD 2>/dev/null || echo unknown)"
cat > "$WORK/manifest.txt" <<EOF
备份时间：${TIMESTAMP}
Git 版本：${git_rev}
数据库大小：${db_size} 字节
脚本版本：deploy/backup.sh v1
EOF

# ---------------------------------------------------------------------------
# 4. 打包
# ---------------------------------------------------------------------------
ARCHIVE="${BACKUP_DIR}/blog-backup-${TIMESTAMP}.tar.gz"
log "打包归档：$ARCHIVE"
tar -czf "$ARCHIVE" -C "$WORK" .
chmod 600 "$ARCHIVE"

# ---------------------------------------------------------------------------
# 5. 保留策略
# ---------------------------------------------------------------------------
count=0
while IFS= read -r old; do
  rm -f "$old"
  count=$((count + 1))
done < <(
  find "$BACKUP_DIR" -maxdepth 1 -name 'blog-backup-*.tar.gz' -printf '%T@\t%p\n' \
    | sort -rn \
    | tail -n +$((KEEP + 1)) \
    | cut -f2-
)

archive_size="$(du -h "$ARCHIVE" | cut -f1)"
remaining="$(find "$BACKUP_DIR" -maxdepth 1 -name 'blog-backup-*.tar.gz' | wc -l)"
log "备份完成：$ARCHIVE（$archive_size）"
log "当前保留份数：$remaining / $KEEP"
