# 至知 Journal — Flask + Vue 个人博客

一个报刊排版风格的个人博客：Vue 3 + Vite 前台，Flask 后端，SQLite 存储，内置单管理员写作后台。支持 Markdown 写作工作流、自动保存、历史版本、媒体库与回收站，前台自带 SEO（OG 标签、Atom feed、sitemap、robots.txt）。

## 功能特性

**前台**
- 报刊式首页：封面、最新文章大图卡、热点排行、归档与标签筛选
- 文章详情：阅读进度、目录跟随、代码高亮与复制、图片灯箱、上一篇/下一篇、相关推荐
- 关于页、404 页、打印样式（print 适配）
- SEO：文章页注入 title/description/OG/canonical；`/feed.xml`、`/sitemap.xml`、`/robots.txt`

**后台（单管理员）**
- 紧凑写作台：写作 / 分栏 / 预览三种视图，Markdown 工具栏与快捷键
- 自动保存：本地草稿缓存 + 服务器同步 + 版本冲突检测 + 离线重试
- 发布预检：服务端校验错误/提醒，定位到具体字段
- 历史版本：发布、下架、回收等关键节点自动留档，支持预览与恢复
- 媒体库：图片上传（表单 / 粘贴 / 拖拽）、素材抽屉、文章引用关系
- 稿件总览：搜索、状态筛选、排序、批量操作、内容健康度与待办提醒
- 站点资料维护：名称、标语、简介、联系方式（前台实时预览卡片）

**数据**
- SQLite 单文件存储，启动时自动建表与幂等迁移
- 文章回收站保留 30 天，可恢复
- 正文图片上传至 `storage/media`（`storage/avatars` 仅保留历史文件）

## 技术栈与架构

| 端 | 技术 |
|---|---|
| 前端 | Vue 3（`<script setup>`）、Vue Router、Vite 6、highlight.js |
| 后端 | Flask、SQLite（WAL）、Markdown（extra/fenced_code/tables/nl2br + HTML 白名单消毒）、Pillow（图片校验/压缩） |
| 部署 | Gunicorn + systemd + Nginx + certbot（HTTPS），uv/pip 依赖管理 |

后端采用「路由 — 服务 — 仓储」三层 + 工具模块的工程化拆分：

```text
backend/src/blog/
├── app.py              # 应用工厂：配置、安全钩子、错误处理、蓝图注册
├── config.py           # 启动配置读取与生产强校验
├── security.py         # 会话鉴权、CSRF、登录限流、安全响应头
├── serializers.py      # API 载荷裁剪
├── seo.py              # Atom feed / sitemap / OG 注入
├── uploads.py          # 上传校验、图片压缩、公开路径白名单
├── validation.py       # 表单字段长度校验
├── routes/             # 路由层：public / feed / spa / admin_auth / admin_pages / admin_posts / admin_api
├── services/           # 服务层：post / media / profile / dashboard / import 业务编排
├── repository/         # 仓储层：database / posts / revisions / profile / media（纯 SQLite 访问）
├── markdown_tools/     # 工具层：renderer（渲染+消毒）/ frontmatter / analysis
└── store.py            # 兼容门面：BlogStore 委托各服务（保留旧接口）
```

前端按职责拆分：

```text
frontend/src/
├── services/       # http.js（请求基建）+ api.js（端点）
├── lib/            # highlight.js（语言注册）、articleEnhancer.js（正文 DOM 增强）
├── composables/    # useSite / usePost / usePosts / useReveal / usePageMeta / useFormat
│                   # useReadingProgress / useTableOfContents / useLightbox
├── components/     # home/、post/、posts/ 子目录 + SiteHeader / SiteFooter / AsyncState 等
├── views/          # HomeView / PostsView / PostView / AboutView / NotFoundView（编排层）
└── styles/         # editorial.css 聚合 12 个按层叠顺序导入的样式模块
```

管理后台静态资源同样模块化：`static/admin/css/` 按页面拆分（base/dashboard/write/media/profile），`static/admin/js/write/` 为 ES Modules（dom/util/api/save-state/editor/preview/workspace/panels/autosave/media/importer/publish/revisions + main 装配）。

## 目录结构

```text
backend/      服务端：可安装 Python 包（src/blog），Jinja 后台模板与静态资源，pytest 测试
frontend/     前端：Vue 3 SPA，构建产物输出到 frontend/dist
deploy/       Linux 部署：deploy.sh、systemd/Nginx 示例、备份与恢复脚本
scripts/      Windows 本地脚本：dev.ps1、verify.ps1、backup.ps1
storage/      SQLite 数据库与上传文件（运行时数据，不入库）
storage-backups/  备份产物（Linux 备份脚本输出）
docs/         上线检查清单等文档
```

## 本地开发

要求：Python ≥ 3.10、Node ≥ 18、[uv](https://docs.astral.sh/uv/)（可选，未安装时用 pip）。

```bash
# 1. 后端依赖（虚拟环境位于 backend/.venv）
uv sync --directory backend --group dev --group prod

# 2. 启动后端（自动加载根目录 .env）
backend/.venv/bin/python -m blog
# Windows: backend\.venv\Scripts\python.exe -m blog

# 3. 前端
cd frontend
npm install
npm run dev        # http://127.0.0.1:5173，Vite 代理 /api 到后端
```

也可以一键启动前后端：`.\scripts\dev.ps1`。

## 环境变量（.env）

复制 `.env.example` 为 `.env` 后按需修改，后端启动时自动读取：

| 变量 | 默认 | 说明 |
|---|---|---|
| `BLOG_SECRET_KEY` | dev 默认值 | 会话签名密钥，生产至少 32 位随机值 |
| `BLOG_ADMIN_PASSWORD` | `admin123456` | 后台登录密码，生产至少 12 位强密码 |
| `BLOG_ADMIN_PREFIX` | `/admin` | 后台入口路径，生产改为不易猜测的路径 |
| `BLOG_HOST` / `BLOG_PORT` | `127.0.0.1` / `5000` | 开发服务器监听地址 |
| `BLOG_DEBUG` | `false` | 生产必须 `false` |
| `BLOG_COOKIE_SECURE` | `false` | 站点走 HTTPS 时必须 `true` |
| `BLOG_PUBLIC_BASE_URL` | 空 | 公开域名，如 `https://blog.example.com`（RSS/sitemap/OG 使用） |
| `BLOG_REQUIRE_PUBLIC_BASE_URL` | `false` | 上线时设 `true`，运行时强校验公开域名 |
| `BLOG_TRUSTED_PROXY_COUNT` | `0` | Nginx 反向代理下设为 `1`（登录限流取真实客户端 IP） |
| `BLOG_DATABASE_PATH` | `storage/blog.db` | 相对路径按项目根目录解析 |
| `BLOG_MAX_UPLOAD_BYTES` | 10 MB | 单次上传上限（与 Nginx `client_max_body_size` 对应） |
| `BLOG_MAX_IMAGE_BYTES` / `BLOG_MAX_IMAGE_PIXELS` | 5 MB / 2000 万像素 | 图片校验上限 |
| `BLOG_SESSION_LIFETIME_SECONDS` | 8 小时 | 后台会话时长 |
| `BLOG_LOGIN_MAX_ATTEMPTS` / `BLOG_LOGIN_RATE_WINDOW_SECONDS` | 5 / 300 | 登录限流 |

> 生产模式下启动会做强校验：弱密钥、弱密码、默认后台路径、缺 HTTPS 域名等都会直接拒绝启动。

## 测试

```bash
backend/.venv/bin/python -m pytest backend/tests -q
# Windows 下如遇临时目录权限问题：--basetemp=.tmp/pytest
```

测试覆盖：后端集成测试（API、后台流程、数据库迁移、安全）、模块级测试（markdown 渲染与消毒、上传管线、序列化、SEO、安全配置）。

## 构建与发布验证

```bash
cd frontend
npm run build          # 产物输出 frontend/dist，由 Flask 自动托管
```

Windows 一键验证（测试 + 构建 + API 冒烟 + 生产配置检查）：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1 -StrictLaunch   # 上线前严格模式
```

## Linux + Nginx 部署

要求：Ubuntu/Debian，Python ≥ 3.10（含 venv）、Node ≥ 18、nginx、certbot（HTTPS 时）。完整清单见 `docs/launch-checklist.md`。

```bash
# 1. 获取代码
sudo mkdir -p /opt/blog && sudo chown $USER /opt/blog
git clone <仓库地址> /opt/blog && cd /opt/blog

# 2. 准备生产配置
cp .env.example .env
nano .env     # 至少修改：BLOG_SECRET_KEY / BLOG_ADMIN_PASSWORD / BLOG_ADMIN_PREFIX
              # BLOG_PUBLIC_BASE_URL=https://域名 / BLOG_REQUIRE_PUBLIC_BASE_URL=true / BLOG_COOKIE_SECURE=true

# 3. 一键部署（依赖 + 测试 + 构建 + systemd 服务 + Nginx 反代 + TLS 证书 + 每日备份 timer）
DOMAIN=你的域名 INSTALL_NGINX=1 INSTALL_TLS=1 TLS_EMAIL=你的邮箱 deploy/deploy.sh
```

可选参数（环境变量传入）：`SERVICE_NAME`（默认 blog）、`SERVICE_USER`、`APP_PORT`（8000）、`GUNICORN_WORKERS`（2）、`RUN_TESTS`、`INSTALL_SERVICE`、`INSTALL_NGINX`、`INSTALL_TLS`、`TLS_EMAIL`、`BACKUP_KEEP`（7）。

脚本行为说明：

- 使用 `INSTALL_NGINX=1` 时自动在 `.env` 写入 `BLOG_TRUSTED_PROXY_COUNT=1`
- Nginx 配置写入 `/etc/nginx/sites-available/blog.conf`（gzip、10m 上传上限、转发头），`nginx -t` 通过后 reload
- 证书签发后 Nginx 配置由 certbot 托管，后续重跑脚本不会覆盖 TLS 配置
- systemd 服务以独立账号运行并启用沙箱加固，开机自启
- 无域名临时体验：`.env` 中 `BLOG_PUBLIC_BASE_URL` 留空、`BLOG_REQUIRE_PUBLIC_BASE_URL=false`、`BLOG_COOKIE_SECURE=false`，`DOMAIN=服务器IP deploy/deploy.sh`（仅 HTTP）

手动配置 Nginx 可参考 `deploy/nginx.conf.example`，systemd 单元参考 `deploy/blog.service.example`。

## 备份与恢复

```bash
# Linux：手动备份（数据库一致性快照 + avatars/media）
bash deploy/backup.sh

# 恢复（恢复前自动创建回滚点）
bash deploy/restore.sh storage-backups/blog-backup-<时间戳>.tar.gz --yes
```

- 每日自动备份：systemd timer（每天 03:20 ±15min，保留 `BACKUP_KEEP` 份）
- 本地备份：`./scripts/backup.ps1`（Windows）
- 升级或迁移前务必备份 `storage/blog.db`、`storage/media`（含历史 `storage/avatars`）

## 常见问题

- **后台登录不上（已配 HTTPS）**：确认 `BLOG_COOKIE_SECURE=true` 且访问的是 https 地址；HTTP 下登录会被安全策略拒绝。
- **上传图片报 413**：`BLOG_MAX_UPLOAD_BYTES` 与 Nginx `client_max_body_size`（默认 10m）需匹配。
- **登录限流误判**：Nginx 反代场景确认 `BLOG_TRUSTED_PROXY_COUNT=1`。
- **修改已发布文章**：草稿修改不会影响线上，点击「发布更新」后生效；重要节点会留历史版本，可随时恢复。

## 安全提醒

- 生产环境必须修改 `BLOG_SECRET_KEY`（≥32 位随机）、`BLOG_ADMIN_PASSWORD`（强密码）、`BLOG_ADMIN_PREFIX`（非默认路径）
- `.env` 已被 gitignore，切勿提交真实密钥
- 使用 Nginx + Gunicorn 生产部署，不要用 Flask 开发服务器对外服务
