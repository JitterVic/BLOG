# 上线检查清单

这份清单用于把仓库从“本地可运行”推进到“可以安全上线”。

## 1. 生产配置

在正式环境的 `.env` 中确认以下值：

- `BLOG_SECRET_KEY`：随机生成，长度至少 32 位
- `BLOG_ADMIN_PASSWORD`：强密码，长度至少 12 位
- `BLOG_ADMIN_PREFIX`：非默认后台路径，例如 `/hidden-admin`
- `BLOG_PUBLIC_BASE_URL`：必须设置为真实的 HTTPS 公开域名，例如 `https://blog.example.com`
- `BLOG_REQUIRE_PUBLIC_BASE_URL=true`：上线时启用运行时强校验，防止漏配公开域名
- `BLOG_COOKIE_SECURE=true`：只要站点对外使用 HTTPS，就必须开启
- `BLOG_DEBUG=false`

## 2. 发布前验证

在仓库根目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\一键验证.ps1 -StrictLaunch
```

如果任一项不符合上线要求，脚本会直接失败并列出原因；严格模式会要求运行时配置 `BLOG_REQUIRE_PUBLIC_BASE_URL=true`。

## 3. Linux 一键部署

生产 `.env` 准备好后，在 Linux 服务器仓库根目录运行（建议用有 sudo 权限的普通管理员账号）：

```bash
chmod +x deploy.sh
./deploy.sh
```

如果要让脚本同时安装 Nginx 反向代理配置：

```bash
DOMAIN=blog.example.com INSTALL_NGINX=1 ./deploy.sh
```

脚本会安装 `requirements-prod.txt`、构建 `frontend/dist/`、执行配置校验，并在有 systemd 的服务器上安装/重启服务。

## 4. 构建与冒烟验证

严格检查通过后，再确认：

- `python -m pytest backend/tests -q` 通过
- `cd frontend && npm run build` 通过
- `frontend/dist/` 已生成最新产物
- `/api/health` 和 `/api/posts` 正常返回

## 5. 上线前的人工核对

- 登录后台确认首页资料、关于页、联系方式、头像、精选文章都已更新
- 确认文章列表、草稿、回收站状态符合预期
- 确认备份脚本可用，且 `storage/blog.db`、`storage/avatars`、`storage/media` 已备份
- 确认生产环境使用 Nginx + Gunicorn / Waitress 等方式，而不是 Flask 开发服务器

## 6. 回滚准备

- 保留最近一次数据库备份
- 保留最近一次静态构建产物
- 保留反向代理和服务启动配置的上一版


