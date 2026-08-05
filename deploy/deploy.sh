#!/usr/bin/env bash
set -Eeuo pipefail

# ---------------------------------------------------------------------------
# 可配置变量（均可通过环境变量覆盖）
# ---------------------------------------------------------------------------
APP_DIR="${APP_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
SERVICE_NAME="${SERVICE_NAME:-blog}"
SERVICE_USER="${SERVICE_USER:-${SUDO_USER:-$(id -un)}}"
SERVICE_GROUP="${SERVICE_GROUP:-}"
APP_HOST="${APP_HOST:-127.0.0.1}"
APP_PORT="${APP_PORT:-8000}"
GUNICORN_WORKERS="${GUNICORN_WORKERS:-2}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
NPM_BIN="${NPM_BIN:-npm}"
RUN_TESTS="${RUN_TESTS:-1}"
INSTALL_SERVICE="${INSTALL_SERVICE:-1}"
INSTALL_NGINX="${INSTALL_NGINX:-0}"
DOMAIN="${DOMAIN:-}"
INSTALL_TLS="${INSTALL_TLS:-0}"
TLS_EMAIL="${TLS_EMAIL:-}"
HEALTH_PATH="${HEALTH_PATH:-/api/health}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-60}"
INSTALL_BACKUP_TIMER="${INSTALL_BACKUP_TIMER:-}"
BACKUP_KEEP="${BACKUP_KEEP:-7}"
MIN_NODE_MAJOR="${MIN_NODE_MAJOR:-18}"

# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------
log() { printf '\033[1;36m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33mWARN: %s\033[0m\n' "$*"; }
fail() { printf '\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "缺少命令：$1（请先安装后重试）"
}

# 以 root 或 sudo 执行命令
sudo_cmd() {
  if [[ "${EUID}" -eq 0 ]]; then
    "$@"
  else
    need_cmd sudo
    sudo "$@"
  fi
}

# 以服务账号执行命令（root 用 runuser，否则用 sudo -u）
as_service_user() {
  if [[ "${EUID}" -eq 0 ]]; then
    runuser -u "$SERVICE_USER" -- "$@"
  else
    need_cmd sudo
    sudo -u "$SERVICE_USER" "$@"
  fi
}

# ---------------------------------------------------------------------------
# 前置检查
# ---------------------------------------------------------------------------
preflight() {
  log "前置环境检查"
  need_cmd "$PYTHON_BIN"
  need_cmd "$NPM_BIN"
  need_cmd node
  need_cmd curl
  need_cmd tar

  "$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' \
    || fail "需要 Python 3.10 及以上版本（后端使用了 str | None 类型注解）"

  "$PYTHON_BIN" -c 'import venv, ensurepip' >/dev/null 2>&1 \
    || fail "缺少 venv 模块，请先执行：sudo apt install -y python3-venv"

  local node_major
  node_major="$(node -v | sed -e 's/^v//' -e 's/\..*$//')"
  [[ "$node_major" -ge "$MIN_NODE_MAJOR" ]] \
    || fail "Vite 6 需要 Node.js ${MIN_NODE_MAJOR} 及以上，当前为 $(node -v)"

  # 默认 SERVICE_GROUP
  if [[ -z "$SERVICE_GROUP" ]]; then
    SERVICE_GROUP="$(id -gn "$SERVICE_USER")"
  fi
}

# ---------------------------------------------------------------------------
# .env 文件处理
# ---------------------------------------------------------------------------
ensure_env_file() {
  if [[ ! -f ".env" ]]; then
    cp .env.example .env
    fail "已生成 .env，请先填写生产配置后重新运行 deploy.sh"
  fi
}

# INSTALL_NGINX=1 时自动写入 BLOG_TRUSTED_PROXY_COUNT=1
ensure_trusted_proxy_count() {
  [[ "$INSTALL_NGINX" == "1" ]] || return 0
  if ! grep -q '^BLOG_TRUSTED_PROXY_COUNT=' .env; then
    printf '\n# Nginx 反向代理层数（由 deploy.sh 自动写入）\nBLOG_TRUSTED_PROXY_COUNT=1\n' >> .env
    log "已在 .env 中写入 BLOG_TRUSTED_PROXY_COUNT=1"
  elif ! grep -q '^BLOG_TRUSTED_PROXY_COUNT=1' .env; then
    warn "检测到 BLOG_TRUSTED_PROXY_COUNT 不是 1，反向代理下的登录限流可能不准确"
  fi
}

# ---------------------------------------------------------------------------
# Python 虚拟环境与依赖
# ---------------------------------------------------------------------------
setup_venv() {
  log "创建/更新 Python 虚拟环境"
  "$PYTHON_BIN" -m venv .venv
  .venv/bin/python -m pip install --upgrade pip
  .venv/bin/python -m pip install -r requirements-prod.txt
}

run_tests() {
  if [[ "$RUN_TESTS" == "1" ]]; then
    log "运行 pytest 后端回归测试"
    .venv/bin/python -m pip install 'pytest>=8,<10'
    PYTHONPATH="$APP_DIR/backend" .venv/bin/python -m pytest backend/tests -q -p no:cacheprovider
  else
    warn "已跳过后端测试（RUN_TESTS=$RUN_TESTS）"
  fi
}

# ---------------------------------------------------------------------------
# 上线配置校验（复用 env_loader + import app，单一事实来源）
# ---------------------------------------------------------------------------
validate_launch_env() {
  log "校验 .env 上线配置"
  # INSTALL_SERVICE=1 时以服务账号执行，让 import app 的建库副作用创建属于服务账号的文件
  local python_runner
  if [[ "$INSTALL_SERVICE" == "1" ]] && [[ "$SERVICE_USER" != "$(id -un)" ]]; then
    python_runner=(as_service_user "$APP_DIR/.venv/bin/python")
  else
    python_runner=("$APP_DIR/.venv/bin/python")
  fi

  "${python_runner[@]}" - <<'PY'
import sys
from pathlib import Path

root = Path.cwd()
if not (root / ".env").exists():
    raise SystemExit("缺少 .env：请先复制 .env.example 并填写生产配置。")

sys.path.insert(0, str(root / "backend"))
from env_loader import load_env_file, env_bool
load_env_file(root / ".env")

issues = []
if env_bool("BLOG_DEBUG", False):
    issues.append("BLOG_DEBUG 必须为 false")
if not env_bool("BLOG_REQUIRE_PUBLIC_BASE_URL", False):
    issues.append("BLOG_REQUIRE_PUBLIC_BASE_URL 必须为 true")
if issues:
    raise SystemExit("上线配置检查未通过：\n- " + "\n- ".join(issues))

import app  # 触发密钥/密码/后台路径/HTTPS/Cookie 的运行时校验，并创建数据库结构
print("上线配置校验通过")
PY
}

# ---------------------------------------------------------------------------
# 前端构建
# ---------------------------------------------------------------------------
build_frontend() {
  log "安装前端依赖并执行生产构建"
  pushd frontend >/dev/null
  if [[ -f package-lock.json ]]; then
    "$NPM_BIN" ci
  else
    "$NPM_BIN" install
  fi
  "$NPM_BIN" run build
  popd >/dev/null
}

# ---------------------------------------------------------------------------
# 服务账号与权限
# ---------------------------------------------------------------------------
ensure_service_user() {
  [[ "$INSTALL_SERVICE" == "1" ]] || return 0
  id -u "$SERVICE_USER" >/dev/null 2>&1 && return 0
  log "创建服务账号：$SERVICE_USER"
  sudo_cmd useradd --system --home-dir "$APP_DIR" --shell /usr/sbin/nologin "$SERVICE_USER"
}

fix_ownership() {
  [[ "$INSTALL_SERVICE" == "1" ]] || return 0
  log "修正运行时目录与密钥文件权限"
  mkdir -p storage storage-backups
  # .env：属主保持部署者，组改为服务组，chmod 640 → 服务账号经组可读，部署者重跑时也可读
  sudo_cmd chown "$(id -un)":"$SERVICE_GROUP" .env
  sudo_cmd chmod 640 .env
  # storage 目录归服务账号
  sudo_cmd chown -R "$SERVICE_USER":"$SERVICE_GROUP" storage storage-backups
  sudo_cmd chmod -R u=rwX,g=,o= storage storage-backups
  # 自检
  as_service_user test -r "$APP_DIR/.env" \
    || fail "服务账号 $SERVICE_USER 无法读取 .env，请把仓库放到 /opt/blog 等可访问目录后重试"
  as_service_user test -x "$APP_DIR/.venv/bin/gunicorn" \
    || fail "服务账号 $SERVICE_USER 无法执行 .venv/bin/gunicorn，请检查上级目录权限"
}

# ---------------------------------------------------------------------------
# systemd 服务
# ---------------------------------------------------------------------------
write_systemd_unit() {
  local unit_path="/etc/systemd/system/${SERVICE_NAME}.service"
  local unit_content
  unit_content=$(cat <<EOF
[Unit]
Description=个人博客 Flask 应用（${SERVICE_NAME}）
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${SERVICE_USER}
Group=${SERVICE_GROUP}
WorkingDirectory=${APP_DIR}
Environment=PYTHONDONTWRITEBYTECODE=1
Environment=PYTHONUNBUFFERED=1
ExecStart=${APP_DIR}/.venv/bin/gunicorn --chdir ${APP_DIR}/backend --bind ${APP_HOST}:${APP_PORT} --workers ${GUNICORN_WORKERS} --timeout 120 --keep-alive 5 --max-requests 1000 --max-requests-jitter 50 --worker-tmp-dir /dev/shm --access-logfile - --error-logfile - app:app
Restart=always
RestartSec=5

# 安全加固
NoNewPrivileges=true
PrivateTmp=true
PrivateDevices=true
ProtectSystem=full
ProtectHome=read-only
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictSUIDSGID=true
RestrictRealtime=true
LockPersonality=true
UMask=0077
ReadWritePaths=${APP_DIR}/storage ${APP_DIR}/storage-backups

[Install]
WantedBy=multi-user.target
EOF
)

  log "写入/更新 systemd 单元：${unit_path}"
  printf '%s\n' "$unit_content" | sudo_cmd tee "$unit_path" >/dev/null
  sudo_cmd systemctl daemon-reload
  sudo_cmd systemctl enable "$SERVICE_NAME" >/dev/null
  sudo_cmd systemctl restart "$SERVICE_NAME"

  if ! sudo_cmd systemctl is-active --quiet "$SERVICE_NAME"; then
    warn "服务启动失败，最近 50 条日志："
    sudo_cmd journalctl -u "$SERVICE_NAME" -n 50 --no-pager || true
    fail "systemd 服务 ${SERVICE_NAME} 未成功启动，请根据上面的日志排查"
  fi
  log "systemd 服务已启动并设为开机自启"
}

# ---------------------------------------------------------------------------
# Nginx 配置
# ---------------------------------------------------------------------------
write_nginx_conf() {
  [[ -n "$DOMAIN" ]] || fail "DOMAIN is required when INSTALL_NGINX=1"
  need_cmd nginx
  local conf_path="/etc/nginx/sites-available/${SERVICE_NAME}.conf"
  local enabled_path="/etc/nginx/sites-enabled/${SERVICE_NAME}.conf"

  # certbot 已接管时跳过覆盖（避免每次部署清掉 TLS 配置）
  if [[ -f "$conf_path" ]] && grep -q "managed by Certbot" "$conf_path"; then
    warn "Certbot 已接管 Nginx 配置，跳过覆盖（如需重置请删除 $conf_path 后重跑）"
    return 0
  fi

  local conf_content
  conf_content=$(cat <<EOF
server {
    listen 80;
    server_name ${DOMAIN};

    server_tokens off;
    client_max_body_size 10m;
    proxy_read_timeout 60s;
    proxy_connect_timeout 5s;

    gzip on;
    gzip_proxied any;
    gzip_types text/css application/javascript application/json application/atom+xml text/xml;

    location / {
        proxy_pass http://${APP_HOST}:${APP_PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF
)

  log "写入/更新 Nginx 配置：${conf_path}"
  printf '%s\n' "$conf_content" | sudo_cmd tee "$conf_path" >/dev/null
  sudo_cmd ln -sfn "$conf_path" "$enabled_path"
  sudo_cmd nginx -t
  sudo_cmd systemctl reload nginx
}

# ---------------------------------------------------------------------------
# TLS 证书（certbot）
# ---------------------------------------------------------------------------
install_tls() {
  [[ "$INSTALL_TLS" == "1" ]] || return 0
  [[ -n "$DOMAIN" ]] || fail "INSTALL_TLS=1 时必须提供 DOMAIN"
  [[ -n "$TLS_EMAIL" ]] || fail "INSTALL_TLS=1 时必须提供 TLS_EMAIL"
  if ! command -v certbot >/dev/null 2>&1; then
    warn "未检测到 certbot，已跳过证书签发。请执行以下命令后重跑："
    warn "  sudo apt install -y certbot python3-certbot-nginx"
    warn "  INSTALL_NGINX=1 INSTALL_TLS=1 DOMAIN=$DOMAIN TLS_EMAIL=$TLS_EMAIL ./deploy.sh"
    return 0
  fi
  log "使用 certbot 签发 TLS 证书：$DOMAIN"
  sudo_cmd certbot --nginx -d "$DOMAIN" --agree-tos -m "$TLS_EMAIL" --non-interactive --redirect
  sudo_cmd nginx -t && sudo_cmd systemctl reload nginx
}

# ---------------------------------------------------------------------------
# 定时备份（提交 7 实现 deploy/backup.sh，此处为 systemd timer 安装）
# ---------------------------------------------------------------------------
install_backup_timer() {
  local do_install="${INSTALL_BACKUP_TIMER:-$INSTALL_SERVICE}"
  [[ "$do_install" == "1" ]] || return 0
  [[ -f "$APP_DIR/deploy/backup.sh" ]] || { warn "未找到 deploy/backup.sh，跳过定时备份安装"; return 0; }

  local svc_path="/etc/systemd/system/${SERVICE_NAME}-backup.service"
  local timer_path="/etc/systemd/system/${SERVICE_NAME}-backup.timer"

  log "安装定时备份 systemd timer"

  cat <<EOF | sudo_cmd tee "$svc_path" >/dev/null
[Unit]
Description=博客数据库与媒体定时备份（${SERVICE_NAME}）

[Service]
Type=oneshot
User=${SERVICE_USER}
Group=${SERVICE_GROUP}
Environment=APP_DIR=${APP_DIR}
Environment=KEEP=${BACKUP_KEEP}
ExecStart=/bin/bash ${APP_DIR}/deploy/backup.sh
NoNewPrivileges=true
PrivateTmp=true
PrivateDevices=true
ProtectSystem=full
ProtectHome=read-only
ReadWritePaths=${APP_DIR}/storage-backups ${APP_DIR}/storage
EOF

  cat <<EOF | sudo_cmd tee "$timer_path" >/dev/null
[Unit]
Description=每日备份 ${SERVICE_NAME}（03:20 附近）

[Timer]
OnCalendar=*-*-* 03:20:00
Persistent=true
RandomizedDelaySec=900

[Install]
WantedBy=timers.target
EOF

  sudo_cmd systemctl daemon-reload
  sudo_cmd systemctl enable "${SERVICE_NAME}-backup.timer" >/dev/null
  sudo_cmd systemctl start "${SERVICE_NAME}-backup.timer"
  log "定时备份已安装（每天 03:20 ±15min，保留 ${BACKUP_KEEP} 份）"
}

# ---------------------------------------------------------------------------
# 健康检查
# ---------------------------------------------------------------------------
health_probe() {
  [[ "$INSTALL_SERVICE" == "1" ]] || return 0
  local url="http://${APP_HOST}:${APP_PORT}${HEALTH_PATH}"
  local deadline=$((SECONDS + HEALTH_TIMEOUT))
  log "健康检查：$url"
  while ((SECONDS < deadline)); do
    if curl -fsS --max-time 3 "$url" | grep -q '"status"'; then
      log "健康检查通过"
      return 0
    fi
    sleep 2
  done
  warn "健康检查失败，最近 50 条服务日志："
  sudo_cmd journalctl -u "$SERVICE_NAME" -n 50 --no-pager || true
  fail "服务在 ${HEALTH_TIMEOUT} 秒内没有通过健康检查，请根据上面的日志排查"
}

# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
main() {
  cd "$APP_DIR"
  log "开始 Linux 一键部署：$APP_DIR"

  preflight
  ensure_env_file
  chmod 600 .env
  ensure_trusted_proxy_count

  setup_venv
  run_tests

  ensure_service_user
  fix_ownership
  validate_launch_env

  build_frontend

  if [[ "$INSTALL_SERVICE" == "1" ]]; then
    if command -v systemctl >/dev/null 2>&1; then
      write_systemd_unit
    else
      warn "未检测到 systemctl，跳过 systemd 服务安装"
    fi
  else
    warn "已跳过 systemd 服务安装（INSTALL_SERVICE=$INSTALL_SERVICE）"
  fi

  install_backup_timer

  if [[ "$INSTALL_NGINX" == "1" ]]; then
    write_nginx_conf
    install_tls
  else
    warn "未安装 Nginx 配置；如需自动写入，请使用 INSTALL_NGINX=1 DOMAIN=你的域名"
  fi

  health_probe

  log "部署完成"
  printf '本地地址：http://%s:%s\n' "$APP_HOST" "$APP_PORT"
  printf 'systemd 服务：%s\n' "$SERVICE_NAME"
  printf '查看状态：sudo systemctl status %s\n' "$SERVICE_NAME"
  printf '查看日志：sudo journalctl -u %s -f\n' "$SERVICE_NAME"

  # TLS 状态提醒
  if [[ "$INSTALL_NGINX" == "1" && "$INSTALL_TLS" != "1" ]]; then
    warn "当前仅配置了 HTTP（80 端口）。如 .env 中 BLOG_COOKIE_SECURE=true，后台将无法登录。"
    warn "建议执行：INSTALL_TLS=1 DOMAIN=$DOMAIN TLS_EMAIL=你的邮箱 ./deploy.sh"
  fi
}

main "$@"
