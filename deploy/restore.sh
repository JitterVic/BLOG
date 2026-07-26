#!/usr/bin/env bash
# deploy/restore.sh — 从备份归档恢复博客数据库与媒体
# 用法：deploy/restore.sh <备份文件.tar.gz> --yes
set -Eeuo pipefail

APP_DIR="${APP_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
SERVICE_NAME="${SERVICE_NAME:-blog}"
SERVICE_USER="${SERVICE_USER:-${SUDO_USER:-$(id -un)}}"
SERVICE_GROUP="${SERVICE_GROUP:-}"
PYTHON_BIN="${PYTHON_BIN:-${APP_DIR}/.venv/bin/python}"
HEALTH_PATH="${HEALTH_PATH:-/api/health}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-60}"
APP_HOST="${APP_HOST:-127.0.0.1}"
APP_PORT="${APP_PORT:-8000}"

log() { printf '\033[1;36m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33mWARN: %s\033[0m\n' "$*"; }
fail() { printf '\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

sudo_cmd() {
  if [[ "${EUID}" -eq 0 ]]; then
    "$@"
  else
    command -v sudo >/dev/null 2>&1 || fail "缺少 sudo"
    sudo "$@"
  fi
}

# ---------------------------------------------------------------------------
# 参数校验
# ---------------------------------------------------------------------------
if [[ "${1:-}" != "--help" && "${1:-}" != "-h" ]]; then
  ARCHIVE="${1:-}"
fi

CONFIRM="${2:-${CONFIRM:-}}"

if [[ -z "$ARCHIVE" || "$CONFIRM" != "--yes" ]]; then
  echo "用法：deploy/restore.sh <备份文件.tar.gz> --yes"
  echo ""
  echo "此操作会停止服务、覆盖当前数据库和媒体文件，请确认备份文件正确。"
  echo "恢复前会自动执行一次备份作为回滚点。"
  exit 1
fi

[[ -f "$ARCHIVE" ]] || fail "备份文件不存在：$ARCHIVE"

if [[ -z "$SERVICE_GROUP" ]]; then
  SERVICE_GROUP="$(id -gn "$SERVICE_USER")"
fi

# ---------------------------------------------------------------------------
# 校验归档内容
# ---------------------------------------------------------------------------
log "校验归档内容"
if ! tar -tzf "$ARCHIVE" | grep -q '\./blog\.db$'; then
  fail "归档中不包含 ./blog.db，这不是有效的博客备份文件"
fi

# ---------------------------------------------------------------------------
# 自动回滚点
# ---------------------------------------------------------------------------
log "创建恢复前回滚点"
if [[ -f "$APP_DIR/deploy/backup.sh" ]]; then
  BACKUP_DIR="${APP_DIR}/storage-backups" bash "$APP_DIR/deploy/backup.sh" || warn "回滚点备份失败（继续恢复）"
else
  warn "未找到 deploy/backup.sh，跳过回滚点创建"
fi

# ---------------------------------------------------------------------------
# 停止服务
# ---------------------------------------------------------------------------
if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
  log "停止服务：$SERVICE_NAME"
  sudo_cmd systemctl stop "$SERVICE_NAME"
else
  warn "服务未运行或无 systemctl，请手动确认没有进程在写入数据库"
fi

# ---------------------------------------------------------------------------
# 解包与校验
# ---------------------------------------------------------------------------
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

log "解包归档"
tar -xzf "$ARCHIVE" -C "$WORK"

log "校验归档数据库完整性"
if ! "$PYTHON_BIN" -c "
import sqlite3, sys
conn = sqlite3.connect(sys.argv[1])
result = conn.execute('PRAGMA integrity_check').fetchone()[0]
conn.close()
if result != 'ok':
    print(f'完整性校验失败：{result}', file=sys.stderr)
    sys.exit(1)
print('完整性校验通过')
" "$WORK/blog.db"; then
  fail "归档中的数据库完整性校验失败，恢复已中止（服务已停止，请手动检查）"
fi

# ---------------------------------------------------------------------------
# 就位
# ---------------------------------------------------------------------------
log "恢复数据库"
STORAGE="${APP_DIR}/storage"
mkdir -p "$STORAGE"

# 先删除残留 WAL/SHM（最关键一步：残留 WAL 会被套用到新库上造成损坏）
rm -f "$STORAGE/blog.db-wal" "$STORAGE/blog.db-shm"
mv -f "$WORK/blog.db" "$STORAGE/blog.db"

# 恢复媒体（覆盖式合并）
for d in avatars media; do
  if [[ -d "$WORK/$d" ]]; then
    log "恢复 $d"
    cp -a "$WORK/$d" "$STORAGE/"
  fi
done

# ---------------------------------------------------------------------------
# 权限
# ---------------------------------------------------------------------------
log "修正文件权限"
sudo_cmd chown -R "$SERVICE_USER":"$SERVICE_GROUP" "$STORAGE"
sudo_cmd chmod -R u=rwX,g=,o= "$STORAGE"

# ---------------------------------------------------------------------------
# 启动服务
# ---------------------------------------------------------------------------
if command -v systemctl >/dev/null 2>&1; then
  log "启动服务：$SERVICE_NAME"
  sudo_cmd systemctl start "$SERVICE_NAME"

  log "健康检查"
  local _url="http://${APP_HOST}:${APP_PORT}${HEALTH_PATH}"
  local _deadline=$((SECONDS + HEALTH_TIMEOUT))
  log "健康检查：$_url"
  while ((SECONDS < _deadline)); do
    if curl -fsS --max-time 3 "$url" 2>/dev/null | grep -q '"status"'; then
      log "恢复完成，服务已正常运行"
      echo ""
      echo "若结果不符合预期，可使用回滚点再次执行本脚本："
      echo "  ls -lt ${APP_DIR}/storage-backups/"
      echo "  deploy/restore.sh <回滚文件.tar.gz> --yes"
      exit 0
    fi
    sleep 2
  done
  warn "健康检查失败，最近 50 条服务日志："
  sudo_cmd journalctl -u "$SERVICE_NAME" -n 50 --no-pager || true
  fail "服务在 ${HEALTH_TIMEOUT} 秒内没有通过健康检查"
else
  log "恢复完成（无 systemctl，请手动启动服务）"
  echo ""
  echo "若结果不符合预期，可使用回滚点再次执行本脚本："
  echo "  ls -lt ${APP_DIR}/storage-backups/"
  echo "  deploy/restore.sh <回滚文件.tar.gz> --yes"
fi
