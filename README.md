# Flask + Vue Personal Blog

一个参考 [PaperGrid](https://github.com/xywml/PaperGrid) 气质重新实现的个人博客项目，前端使用 Vue 3 + Vite，后端使用 Flask，内容存储切换到了 SQLite，并内置了一个可登录的管理后台。

## 现在支持的能力

- 前台博客展示：首页、文章、归档、标签、关于页
- SQLite 数据库存储：站点资料、文章、草稿都落在本地数据库
- 后台管理入口：登录后可以编辑个人资料、更新关于页内容、维护文章
- Markdown 工作流：支持导入 `.md` 文件、在线预览、保存草稿、发布文章
- 文件上传：支持头像上传和正文图片上传

- 历史版本：手动保存、发布、下架和恢复时保留关键节点，支持预览并恢复为草稿
- 文章回收站：删除后保留 30 天，可恢复为草稿，再次发布前不会出现在前台
- 发布预检：同时执行客户端和服务端校验，区分必须修复的错误与可确认继续的提醒
- 媒体库：浏览已上传图片、复制 URL/Markdown，并查看草稿、已发布和回收站文章的引用情况
- 紧凑作者工作台：写作 / 分栏 / 预览、文章设置与媒体抽屉、目录跳转、移动端快速改稿
- 服务器工作副本：修改已发布文章时保持线上版本不变，自动保存待发布修改并支持跨设备继续
- 发布检查与版本比较：错误定位、提醒确认、线上/工作副本/历史版本差异比较和安全恢复

## 目录结构

```text
backend/    服务端：可安装的 Python 包（src/blog），Flask API、管理后台模板、数据库访问层
frontend/   前端：Vue 3 SPA
deploy/     Linux 部署脚本（deploy.sh、systemd/Nginx 示例、备份与恢复）
scripts/    本地开发脚本（dev.ps1、verify.ps1、backup.ps1）
storage/    SQLite 数据库和上传文件（运行时数据，不入库）
```

## 本地运行

1. 安装后端依赖（使用 [uv](https://docs.astral.sh/uv/)，虚拟环境位于 `backend/.venv`）

```bash
uv sync --directory backend --group dev --group prod
```

2. 启动 Flask 后端

```bash
backend/.venv/bin/python -m blog        # Windows: backend\.venv\Scripts\python.exe -m blog
```

3. 安装前端依赖

```bash
cd frontend
npm install
```

4. 启动 Vue 前端开发服务器

```bash
npm run dev
```

前端默认运行在 `http://127.0.0.1:5173`，并通过 Vite 代理访问 Flask 的 `/api`。

## 使用 `.env`

项目根目录已经支持自动读取 `.env`。你只需要直接运行：

```bash
backend/.venv/bin/python -m blog
```

后端会自动加载根目录下的 `.env`，不需要额外传参。

当前可配置的主要变量：

```bash
BLOG_SECRET_KEY=change-me-before-deploy
BLOG_ADMIN_PASSWORD=replace-with-a-strong-password
BLOG_ADMIN_PREFIX=/your-hidden-admin-path
BLOG_DATABASE_PATH=storage/blog.db
BLOG_HOST=127.0.0.1
BLOG_PORT=5000
BLOG_DEBUG=false
BLOG_COOKIE_SECURE=false
BLOG_PUBLIC_BASE_URL=
BLOG_REQUIRE_PUBLIC_BASE_URL=false
```

- `.env` 已加入忽略规则，不会被提交
- `.env.example` 可以作为服务器或新环境的配置模板
- `BLOG_DATABASE_PATH=storage/blog.db` 这种相对路径会自动按项目根目录解析

## 后台入口

默认后台地址：`/admin/login`

默认后台密码：`admin123456`

建议你在部署前一定修改下面这些环境变量：

```bash
BLOG_SECRET_KEY=replace-with-a-random-secret
BLOG_ADMIN_PASSWORD=replace-with-a-strong-password
BLOG_ADMIN_PREFIX=/your-hidden-admin-path
BLOG_DATABASE_PATH=/absolute/path/to/blog.db
BLOG_HOST=127.0.0.1
BLOG_PORT=5000
BLOG_DEBUG=false
BLOG_COOKIE_SECURE=true
BLOG_PUBLIC_BASE_URL=https://example.com
BLOG_REQUIRE_PUBLIC_BASE_URL=true
```

说明：

- `BLOG_ADMIN_PREFIX` 可以把后台入口从 `/admin` 改成你自己的隐藏路径，更接近你想要的“后门入口”
- `BLOG_DATABASE_PATH` 不配置时，默认使用 `storage/blog.db`
- 上传的头像和文章图片默认存放在 `storage/avatars` 和 `storage/media`

## Markdown 发布流程

1. 登录后台，从编辑台继续最近稿件或新建文章
2. 在紧凑写作台输入 Markdown，草稿会自动保存到服务器；无标题内容也会先创建安全草稿
3. 使用“文章设置”维护栏目、标签、Slug、摘要和封面，使用“图片”抽屉上传或选择已有图片
4. 在“写作 / 分栏 / 预览”间切换，或打开登录态全页预览检查最终排版
5. 点击“发布”进入发布检查；错误必须修复，提醒确认后可继续
6. 修改已发布文章时，系统只更新服务器工作副本；点击“发布更新”后才会替换线上版本

升级包含工作副本或媒体元数据表的版本前，先使用仓库备份脚本备份 `storage/blog.db` 和上传目录。数据库迁移为新增表，应用启动时会自动、幂等执行。
## 构建前端

```bash
cd frontend
npm run build
```

构建后，Flask 会自动托管 `frontend/dist` 里的静态文件。

## 发布前一键验证

在准备上线或提交前，可以从仓库根目录运行（完整清单见 `docs/launch-checklist.md`）：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1
```

脚本会依次执行后端 pytest、前端生产构建、临时后端 API 冒烟验证（默认端口 `5055`，并强制 `BLOG_DEBUG=false` 以检查生产启动约束）。如果端口被占用，可以指定 `-Port 5060`；如果只想跳过前端构建，可以加 `-SkipFrontend`。

上线前请额外运行严格配置检查：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1 -StrictLaunch
```

`-StrictLaunch` 会失败退出，直到 `.env` 中的后台密码足够强、后台路径不是默认 `/admin`、`BLOG_PUBLIC_BASE_URL` 已设置为真实的 HTTPS 公开域名、`BLOG_REQUIRE_PUBLIC_BASE_URL=true`，并且 HTTPS 场景下 `BLOG_COOKIE_SECURE=true`。

## Linux 服务器一键部署

如果服务器是 Linux，可以使用 `deploy/deploy.sh`。它会创建/更新 `backend/.venv`（优先用 uv，未安装时回退 pip）、安装生产依赖（含 Gunicorn）、构建前端、校验生产 `.env`，并可安装/重启 systemd 服务。建议在有 sudo 权限的普通管理员账号下执行。

首次运行前先准备 `.env`：

```bash
cp .env.example .env
nano .env
```

至少修改：`BLOG_SECRET_KEY`、`BLOG_ADMIN_PASSWORD`、`BLOG_ADMIN_PREFIX`、`BLOG_PUBLIC_BASE_URL`、`BLOG_REQUIRE_PUBLIC_BASE_URL=true`、`BLOG_COOKIE_SECURE=true`。

常用部署命令：

```bash
deploy/deploy.sh
```

`deploy/deploy.sh` 已自带可执行权限，无需 `chmod +x`。

如果服务器已经安装了 Nginx，并希望脚本同时写入反向代理配置：

```bash
DOMAIN=blog.example.com INSTALL_NGINX=1 deploy/deploy.sh
```

同时用 certbot 签发 TLS 证书：

```bash
DOMAIN=blog.example.com INSTALL_NGINX=1 INSTALL_TLS=1 TLS_EMAIL=you@example.com deploy/deploy.sh
```

可选参数通过环境变量传入：`SERVICE_NAME`、`SERVICE_USER`、`APP_PORT`、`GUNICORN_WORKERS`、`RUN_TESTS`、`INSTALL_SERVICE`、`INSTALL_NGINX`、`INSTALL_TLS`、`TLS_EMAIL`、`BACKUP_KEEP`。详见 `docs/launch-checklist.md`。

deploy/deploy.sh 会自动在 `.env` 中写入 `BLOG_TRUSTED_PROXY_COUNT=1`（当 INSTALL_NGINX=1 时），确保 Nginx 反代下的登录限流使用真实客户端 IP 而非 127.0.0.1。

### 备份与恢复

部署后可使用 Linux 备份/恢复脚本：

```bash
# 手动备份
bash deploy/backup.sh

# 从备份恢复（会先自动创建回滚点）
bash deploy/restore.sh storage-backups/blog-backup-<时间戳>.tar.gz --yes
```

deploy/deploy.sh 默认安装每日定时备份 systemd timer（03:20 ±15min，保留 7 份）。

## 部署前建议

- 修改默认后台密码和 `secret key`（至少 32 位）
- 把 `BLOG_ADMIN_PREFIX` 设成不容易猜到的路径
- 关闭 `BLOG_DEBUG`；如果站点已通过 HTTPS 对外发布，建议将 `BLOG_REQUIRE_PUBLIC_BASE_URL` 设为 `true`，并将 `BLOG_COOKIE_SECURE` 设为 `true`
- 备份 `storage/blog.db` 和 `storage/` 上传目录（可用 `bash deploy/backup.sh`）
- 如果是正式服务器，建议使用 Nginx + Gunicorn 生产部署方式，而不是 Flask 自带开发服务器

## 第一阶段上线需求说明

当前项目已按“个人主页优先 + 轻量上线 + 单管理员后台”的方向推进：

- 首页定位为个人主页，突出头像、昵称、身份、简介、联系方式、精选/最新文章和关注标签。
- 关于页展示更完整的个人资料、动态记录和联系入口。
- 文章页补齐了未发布/不存在文章的友好提示，并优化了 Markdown 图片、表格、代码块等基础阅读样式。
- 后台继续保持单管理员模式，支持维护首页标题、身份、简介、关于页、头像、文章和正文图片。
- 后台文章可以保存为草稿/下架、发布、设置为首页精选，也可以删除。
- 草稿文章不会出现在前台 API 和页面中。

### 上线前检查清单

1. 修改 `.env` 中的 `BLOG_SECRET_KEY` 和 `BLOG_ADMIN_PASSWORD`。
2. 将 `BLOG_ADMIN_PREFIX` 改成不容易猜到的后台路径。
3. 确认 `BLOG_DEBUG=false`。
4. 运行 `powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1 -StrictLaunch`，确认后端测试、前端构建、API 冒烟验证和严格上线配置检查全部通过。
5. 确认 `frontend/dist/` 已由最新构建生成。
6. 备份 `storage/blog.db`、`storage/avatars` 和 `storage/media`。
7. 登录后台确认首页资料、关于页文案、联系方式和已发布文章内容。
