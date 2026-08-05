# 上线检查清单

这份清单用于把仓库从"本地可运行"推进到"可以安全上线"。

## 1. 生产配置

在正式环境的 `.env` 中确认以下值：

- `BLOG_SECRET_KEY`：随机生成，长度至少 32 位
- `BLOG_ADMIN_PASSWORD`：强密码，长度至少 12 位
- `BLOG_ADMIN_PREFIX`：非默认后台路径，例如 `/hidden-admin`
- `BLOG_PUBLIC_BASE_URL`：必须设置为真实的 HTTPS 公开域名，例如 `https://blog.example.com`
- `BLOG_REQUIRE_PUBLIC_BASE_URL=true`：上线时启用运行时强校验，防止漏配公开域名
- `BLOG_COOKIE_SECURE=true`：只要站点对外使用 HTTPS，就必须开启
- `BLOG_DEBUG=false`
- `BLOG_TRUSTED_PROXY_COUNT`：使用 Nginx 反向代理时设为 `1`（deploy/deploy.sh 会自动写入）

## 2. 发布前验证

在仓库根目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1 -StrictLaunch
```

如果任一项不符合上线要求，脚本会直接失败并列出原因；严格模式会要求运行时配置 `BLOG_REQUIRE_PUBLIC_BASE_URL=true`。

## 3. Linux 一键部署

生产 `.env` 准备好后，在 Linux 服务器仓库根目录运行（建议用有 sudo 权限的普通管理员账号）：

```bash
deploy/deploy.sh
```

`deploy/deploy.sh` 已自带可执行权限（通过 `.gitattributes` 保证），无需 `chmod +x`。

如果要让脚本同时安装 Nginx 反向代理配置：

```bash
DOMAIN=blog.example.com INSTALL_NGINX=1 deploy/deploy.sh
```

同时签发 TLS 证书（需要 certbot）：

```bash
DOMAIN=blog.example.com INSTALL_NGINX=1 INSTALL_TLS=1 TLS_EMAIL=you@example.com deploy/deploy.sh
```

可选参数（通过环境变量传入）：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `SERVICE_NAME` | `blog` | systemd 服务名 |
| `SERVICE_USER` | 当前用户 | 运行服务的系统账号（不存在时自动创建） |
| `APP_PORT` | `8000` | Gunicorn 监听端口 |
| `GUNICORN_WORKERS` | `2` | Gunicorn worker 数量 |
| `RUN_TESTS` | `1` | 部署前是否跑 pytest |
| `INSTALL_SERVICE` | `1` | 是否安装 systemd 服务 |
| `INSTALL_NGINX` | `0` | 是否写入 Nginx 配置 |
| `INSTALL_TLS` | `0` | 是否用 certbot 签发证书 |
| `TLS_EMAIL` | — | certbot 注册邮箱（INSTALL_TLS=1 时必填） |
| `BACKUP_KEEP` | `7` | 备份保留份数 |

脚本会：前置环境检查 → 创建 `backend/.venv`（uv 优先，未安装时回退 pip）→ 跑测试 → 校验生产配置 → 修正文件权限 → 构建前端 → 安装/重启 systemd 服务 → 安装备份 timer → 写入 Nginx 配置 → 签发证书 → 健康检查。

## 4. 构建与冒烟验证

严格检查通过后，再确认：

- `backend/.venv/bin/python -m pytest backend/tests -q` 通过
- `cd frontend && npm run build` 通过
- `frontend/dist/` 已生成最新产物
- `/api/health` 和 `/api/posts` 正常返回

## 5. 上线前的人工核对

- 登录后台确认首页资料、关于页、联系方式、头像都已更新
- 确认文章列表、草稿、回收站状态符合预期
- 确认备份脚本可用：`bash deploy/backup.sh`
- 确认定时备份 timer 运行中：`systemctl status blog-backup.timer`
- 确认生产环境使用 Nginx + Gunicorn，而不是 Flask 开发服务器

## 6. 备份与恢复

### Linux 备份

```bash
bash deploy/backup.sh
```

输出到 `storage-backups/blog-backup-<时间戳>.tar.gz`，包含数据库一致性快照和 avatars/media。定时备份由 deploy/deploy.sh 自动安装为 systemd timer（每天 03:20 ±15min）。

### Linux 恢复

```bash
bash deploy/restore.sh storage-backups/blog-backup-<时间戳>.tar.gz --yes
```

恢复前会自动创建回滚点。恢复完成后会重启服务并执行健康检查。

## 7. 回滚准备

- 使用 `deploy/restore.sh <回滚文件.tar.gz> --yes` 恢复到上一个备份点
- 保留最近一次静态构建产物
- 保留反向代理和服务启动配置的上一版
