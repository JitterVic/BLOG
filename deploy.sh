#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${APP_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
SERVICE_NAME="${SERVICE_NAME:-blog}"
SERVICE_USER="${SERVICE_USER:-${SUDO_USER:-$(id -un)}}"
APP_HOST="${APP_HOST:-127.0.0.1}"
APP_PORT="${APP_PORT:-8000}"
GUNICORN_WORKERS="${GUNICORN_WORKERS:-2}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
NPM_BIN="${NPM_BIN:-npm}"
RUN_TESTS="${RUN_TESTS:-1}"
INSTALL_SERVICE="${INSTALL_SERVICE:-1}"
INSTALL_NGINX="${INSTALL_NGINX:-0}"
DOMAIN="${DOMAIN:-}"

log() { printf '\033[1;36m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33mWARN: %s\033[0m\n' "$*"; }
fail() { printf '\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "missing command: $1"
}

sudo_cmd() {
  if [[ "${EUID}" -eq 0 ]]; then
    "$@"
  else
    need_cmd sudo
    sudo "$@"
  fi
}

validate_launch_env() {
  log "校验 .env 上线配置"
  "$APP_DIR/.venv/bin/python" - <<'PY'
from pathlib import Path
import os
import sys

root = Path.cwd()
env_path = root / ".env"
if not env_path.exists():
    raise SystemExit(".env missing; copy .env.example to .env and fill production values first")

values = {}
for raw in env_path.read_text(encoding="utf-8-sig").splitlines():
    line = raw.strip()
    if not line or line.startswith("#"):
        continue
    if line.startswith("export "):
        line = line[7:].strip()
    if "=" not in line:
        continue
    key, value = line.split("=", 1)
    value = value.strip().strip('"').strip("'")
    values[key.strip()] = value

# Process env wins, matching backend/env_loader.py behavior.
values.update({key: value for key, value in os.environ.items() if key.startswith("BLOG_")})

issues = []
secret = values.get("BLOG_SECRET_KEY", "")
password = values.get("BLOG_ADMIN_PASSWORD", "")
prefix = values.get("BLOG_ADMIN_PREFIX", "/admin")
public_base_url = values.get("BLOG_PUBLIC_BASE_URL", "").rstrip("/")
require_public = values.get("BLOG_REQUIRE_PUBLIC_BASE_URL", "false").lower()
cookie_secure = values.get("BLOG_COOKIE_SECURE", "false").lower()
debug = values.get("BLOG_DEBUG", "false").lower()

if debug != "false":
    issues.append("BLOG_DEBUG must be false")
if len(secret) < 32 or secret in {"dev-secret-key-change-me", "change-me-before-deploy", "replace-with-a-random-secret"}:
    issues.append("BLOG_SECRET_KEY must be random and at least 32 characters")
if len(password) < 12 or password in {"123", "123456", "admin", "admin123456", "password", "change-me-before-deploy", "replace-with-a-strong-password"}:
    issues.append("BLOG_ADMIN_PASSWORD must be strong and non-default")
if not prefix.startswith("/") or prefix == "/admin":
    issues.append("BLOG_ADMIN_PREFIX must be a hidden non-default path that starts with /")
if not public_base_url:
    issues.append("BLOG_PUBLIC_BASE_URL must be the real HTTPS public origin")
elif not public_base_url.startswith("https://"):
    issues.append("BLOG_PUBLIC_BASE_URL must start with https://")
if require_public != "true":
    issues.append("BLOG_REQUIRE_PUBLIC_BASE_URL must be true for launch")
if public_base_url.startswith("https://") and cookie_secure != "true":
    issues.append("BLOG_COOKIE_SECURE must be true when public URL is HTTPS")

if issues:
    raise SystemExit("Launch configuration failed:\n- " + "\n- ".join(issues))

sys.path.insert(0, str(root / "backend"))
import app  # noqa: F401 - importing creates the WSGI app and runs runtime config validation
print("launch config ok")
PY
}

write_systemd_unit() {
  local unit_path="/etc/systemd/system/${SERVICE_NAME}.service"
  local unit_content
  unit_content=$(cat <<EOF
[Unit]
Description=Personal Blog Flask App (${SERVICE_NAME})
After=network.target

[Service]
Type=simple
User=${SERVICE_USER}
WorkingDirectory=${APP_DIR}
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart=${APP_DIR}/.venv/bin/gunicorn --chdir ${APP_DIR}/backend --bind ${APP_HOST}:${APP_PORT} --workers ${GUNICORN_WORKERS} --access-logfile - --error-logfile - app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
)

  log "写入/更新 systemd 单元：${unit_path}"
  printf '%s\n' "$unit_content" | sudo_cmd tee "$unit_path" >/dev/null
  sudo_cmd systemctl daemon-reload
  sudo_cmd systemctl enable "$SERVICE_NAME" >/dev/null
  sudo_cmd systemctl restart "$SERVICE_NAME"
  sudo_cmd systemctl --no-pager --full status "$SERVICE_NAME" || true
}

write_nginx_conf() {
  [[ -n "$DOMAIN" ]] || fail "DOMAIN is required when INSTALL_NGINX=1"
  need_cmd nginx
  local conf_path="/etc/nginx/sites-available/${SERVICE_NAME}.conf"
  local enabled_path="/etc/nginx/sites-enabled/${SERVICE_NAME}.conf"
  local conf_content
  conf_content=$(cat <<EOF
server {
    listen 80;
    server_name ${DOMAIN};

    client_max_body_size 10m;

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

main() {
  cd "$APP_DIR"
  log "开始 Linux 一键部署：$APP_DIR"

  need_cmd "$PYTHON_BIN"
  need_cmd "$NPM_BIN"

  if [[ ! -f ".env" ]]; then
    cp .env.example .env
    fail "已生成 .env，请先填写生产配置后重新运行 deploy.sh"
  fi

  log "创建/更新 Python 虚拟环境"
  "$PYTHON_BIN" -m venv .venv
  .venv/bin/python -m pip install --upgrade pip
  .venv/bin/python -m pip install -r requirements-prod.txt

  if [[ "$RUN_TESTS" == "1" ]]; then
    log "运行 pytest 后端回归测试"
    .venv/bin/python -m pip install 'pytest>=8,<10'
    PYTHONPATH="$APP_DIR/backend" .venv/bin/python -m pytest backend/tests -q
  else
    warn "已跳过后端测试（RUN_TESTS=$RUN_TESTS）"
  fi

  validate_launch_env

  log "安装前端依赖并执行生产构建"
  pushd frontend >/dev/null
  if [[ -f package-lock.json ]]; then
    "$NPM_BIN" ci
  else
    "$NPM_BIN" install
  fi
  "$NPM_BIN" run build
  popd >/dev/null

  if [[ "$INSTALL_SERVICE" == "1" ]]; then
    if command -v systemctl >/dev/null 2>&1; then
      write_systemd_unit
    else
      warn "未检测到 systemctl，跳过 systemd 服务安装"
    fi
  else
    warn "已跳过 systemd 服务安装（INSTALL_SERVICE=$INSTALL_SERVICE）"
  fi

  if [[ "$INSTALL_NGINX" == "1" ]]; then
    write_nginx_conf
  else
    warn "未安装 Nginx 配置；如需自动写入，请使用 INSTALL_NGINX=1 DOMAIN=你的域名"
  fi

  log "部署完成"
  printf '本地地址：http://%s:%s\n' "$APP_HOST" "$APP_PORT"
  printf 'systemd 服务：%s\n' "$SERVICE_NAME"
  printf '查看状态：sudo systemctl status %s\n' "$SERVICE_NAME"
}

main "$@"
